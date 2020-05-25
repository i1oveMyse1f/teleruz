# -*- coding: utf-8 -*-

import telebot
import sqlite3
import requests
import datetime
import threading
import time
import json

# TODO: Возможно, найти настройку, которая сделает клавиатуру только из цифр

url_group = "https://ruz.hse.ru/api/search?term={}&type=group"
# example: "https://ruz.hse.ru/api/search?term=БПМИ191&type=group"
url_timetable = "https://ruz.hse.ru/api/schedule/group/{}?start={}&finish={}&lng=1"
# example: "https://ruz.hse.ru/api/schedule/group/11236?start=2020.04.13&finish=2020.04.19&lng=1"

f = open('C:/Users/Administrator/dev/teleruz/token-teleruz.token', 'r')
token = f.readline()

bot = telebot.TeleBot(token)
# telebot.apihelper.proxy = {'https':'socks5://104.248.63.17:30588'}
keyboard_yesno = telebot.types.ReplyKeyboardMarkup(True)
keyboard_yesno.row('Да', 'Нет')

# start sql
con_user = sqlite3.connect("C:/Users/Administrator/dev/teleruz/database.db", check_same_thread=False)
con_user.cursor().execute("""CREATE TABLE IF NOT EXISTS user(
id integer, 
group_label text, 
group_id integer, 
time integer, 
timetable integer, 
timetable_h integer,
timetable_m integer,
is_on integer)""")
con_user.commit()

con_ruz = sqlite3.connect(":memory:", check_same_thread=False)
con_ruz.cursor().execute("""CREATE TABLE IF NOT EXISTS ruz(
id integer, 
info text)""")
con_ruz.commit()

con_time = sqlite3.connect("C:/Users/Administrator/dev/teleruz/time.db", check_same_thread=False)
con_time.cursor().execute("""CREATE TABLE IF NOT EXISTS time(
id integer, 
h integer,
m integer, 
type text)
""")
con_time.commit()
# end of start sql

YES = 'да'
NO = 'нет'
set_all = False
is_reset = False


def my_send_message(chat_id, text, disable_web_page_preview=None, reply_to_message_id=None, reply_markup=None,
                    parse_mode=None, disable_notification=None, timeout=None):
    try:
        return bot.send_message(chat_id, text,
                                disable_web_page_preview, reply_to_message_id, reply_markup, parse_mode,
                                disable_notification, timeout)
    except telebot.apihelper.ApiException:
        print('Какой-то урод забанил бота, удалю его из всех баз!')
        clear_data(chat_id)
    except:
        print('Хз что произошло, посмотри логи')


def rebuild_person(user_id):
    global set_all
    set_all = True
    clear_data(user_id)
    send = my_send_message(user_id, 'Упс, при заполнении ваших данных что-то пошло не так, перепройдите регистрацию.')
    bot.register_next_step_handler(send, register_id)


def to_norm_format(n):
    if len(str(n)) == 1:
        return "0" + str(n)
    else:
        return str(n)


def get_str_date(cur_date):
    return str(cur_date.year) + '.' + to_norm_format(cur_date.month) + '.' + to_norm_format(cur_date.day)


def insert_into_time(user_id, time_user, type_event):
    con_time.cursor().execute("""INSERT INTO time VALUES(?, ?, ?, ?)""",
                              (user_id, time_user.hour, time_user.minute, type_event))
    con_time.commit()


def get_info_user(user_id):
    cur_cursor = con_user.cursor()
    cur_cursor.execute("""SELECT * FROM user WHERE id = ?""", (user_id,))
    return cur_cursor.fetchall()[0]


def get_user_group_label(user_id):
    return get_info_user(user_id)[1]


def get_user_group_id(user_id):
    return get_info_user(user_id)[2]


def get_user_time(user_id):
    return get_info_user(user_id)[3]


def get_user_timetable(user_id):
    return get_info_user(user_id)[4]


def get_user_timetable_h(user_id):
    return get_info_user(user_id)[5]


def get_user_timetable_m(user_id):
    return get_info_user(user_id)[6]


def get_user_on(user_id):
    return get_info_user(user_id)[7]


def have_group(group_id):
    cur_cursor = con_ruz.cursor()
    cur_cursor.execute("""SELECT * FROM ruz WHERE id = ?""", (group_id,))
    return len(cur_cursor.fetchall()) > 0


def clear_time():
    con_time.cursor().execute("""DELETE FROM time""")
    con_time.commit()


def clear_ruz():
    con_ruz.cursor().execute("""DELETE FROM ruz""")
    con_ruz.commit()


def update_db():
    clear_time()
    clear_ruz()
    cursor = con_user.cursor()
    cursor.execute("""SELECT * FROM user""")
    all_users = cursor.fetchall()
    for cur_user in all_users:
        if cur_user[7]:
            try:
                int(cur_user[0])
                int(cur_user[2])
                int(cur_user[3])
                int(cur_user[4])
                int(cur_user[5])
                int(cur_user[6])
                int(cur_user[7])
                add_user(cur_user[0])
            except:
                rebuild_person(cur_user[0])


def add_to_time(cur_user):
    insert_into_time(cur_user[0], datetime.time(cur_user[5], cur_user[6]), 'timetable')
    cur_cursor = con_ruz.cursor()
    cur_cursor.execute("""SELECT * FROM ruz WHERE id = ?""", (cur_user[2],))
    lessons = json.loads(cur_cursor.fetchall()[0][1])
    for lesson in lessons:
        lesson_time = datetime.datetime(1, 1, 1, hour=int(lesson['beginLesson'][0:2]),
                                        minute=int(lesson['beginLesson'][3:5]))
        insert_into_time(cur_user[0], lesson_time - datetime.timedelta(minutes=int(cur_user[3])), 'lesson')


def get_timetable_from_ruz(group_id, date_start, date_finish):
    r = requests.get(url_timetable.format(str(group_id), date_start, date_finish)).json()
    info_group = "["
    for lesson in r:
        info_group += "{"
        info_group += "\"beginLesson\":\"" + lesson['beginLesson'] + "\""
        info_group += ','
        info_group += "\"discipline\":\"" + lesson['discipline'] + "\""
        info_group += ','
        info_group += "\"kindOfWork\":\"" + lesson['kindOfWork'] + "\""
        info_group += ','
        info_group += "\"lecturer\":\"" + lesson['lecturer'] + "\""
        info_group += ','
        info_group += "\"url1\":\"" + lesson['url1'] + "\""
        info_group += "},"
    if len(r) > 0:
        info_group = info_group[:-1]
    info_group += "]"
    return info_group


def add_to_ruz(group_id):
    if not have_group(group_id):
        cur_date = datetime.date.today()
        info_group = get_timetable_from_ruz(group_id, get_str_date(cur_date), get_str_date(cur_date))
        con_ruz.cursor().execute("""INSERT INTO ruz VALUES(?, ?)""", (group_id, info_group))
        con_ruz.commit()


def add_user(user_id):
    cur_user = get_info_user(user_id)
    add_to_ruz(cur_user[2])
    add_to_time(cur_user)


def add_all_events():
    cur_cursor = con_time.cursor()
    cur_cursor.execute("""SELECT * FROM time""")
    all_users = cur_cursor.fetchall()
    for cur_user in all_users:
        add_user(cur_user[0])


def is_on(message):
    cur_cursor = con_user.cursor()
    cur_cursor.execute("""SELECT * FROM user WHERE id = ?""", (message.chat.id,))
    return cur_cursor.fetchall()[0][7]


def have_user(message):
    cur_cursor = con_user.cursor()
    cur_cursor.execute("""SELECT * FROM user WHERE id = ?""", (message.chat.id,))
    return len(cur_cursor.fetchall()) > 0


def register_id(message):
    con_user.cursor().execute("""INSERT INTO user VALUES (?, '', ?, ?, '', ?, ?, ?)""",
                              (message.chat.id, 0, 0, 9, 0, 0))
    con_user.commit()
    my_send_message(message.chat.id, 'Введите свою группу в стандартном формате, например БПМИ191 или БПИ195')
    bot.register_next_step_handler(message, set_group)


def get_id_group(group):
    r = requests.get(url_group.format(group)).json()
    for gr in r:
        if gr['label'] == group:
            return int(gr['id'])
    return -1


def clear_data(user_id):
    con_user.cursor().execute("""DELETE FROM user WHERE id = ?""", (user_id,))
    con_user.commit()
    con_time.cursor().execute("""DELETE FROM time WHERE id = ?""", (user_id,))
    con_time.commit()


def try_clear_data(message):
    global set_all
    if message.text.lower() != YES and message.text.lower() != NO:
        my_send_message(message.chat.id, 'Введите Да или Нет')
        bot.register_next_step_handler(message, try_clear_data)
    elif message.text.lower() == YES:
        clear_data(message.chat.id)
        my_send_message(message.chat.id, 'Данные очищены!',
                        reply_markup=telebot.types.ReplyKeyboardRemove())
        set_all = True
        register_id(message)


def set_group(message):
    global set_all
    global is_reset
    id_group = get_id_group(message.text.upper())
    if id_group == -1:
        my_send_message(message.chat.id, 'Некрректное название группы, попробуйте ещё раз')
        bot.register_next_step_handler(message, set_group)
    else:
        con_user.cursor().execute("""UPDATE user SET group_label = ?, group_id = ? WHERE id = ?""",
                                  (message.text.upper(), id_group, message.chat.id))
        con_user.commit()
        if set_all:
            my_send_message(message.chat.id,
                            'За сколько минут до начала лекции вы хотите, чтобы вам приходило уведомление?')
            bot.register_next_step_handler(message, set_time)
        elif is_reset:
            reset_group(message)


def set_time(message):
    global set_all
    global is_reset
    if not message.text.isdigit() or int(message.text) < 0 or int(message.text) >= 60:
        my_send_message(message.chat.id, 'Введите целое число от 0 до 59')
        bot.register_next_step_handler(message, set_time)
    else:
        con_user.cursor().execute("""UPDATE user SET time = ? WHERE id = ?""", (int(message.text), message.chat.id))
        con_user.commit()
        if set_all:
            my_send_message(message.chat.id,
                            'Хотите ли, чтобы вам проходило уведомление о расписании на сегодняшний день?',
                            reply_markup=keyboard_yesno)
            bot.register_next_step_handler(message, set_timetable)
        elif is_reset:
            reset_time(message)


def set_timetable(message):
    global set_all
    global is_reset
    if message.text.lower() != YES and message.text.lower() != NO:
        my_send_message(message.chat.id, 'Введите Да или Нет')
        bot.register_next_step_handler(message, set_timetable)
    else:
        con_user.cursor().execute("""UPDATE user SET timetable = ? WHERE id = ?""",
                                  (message.text.lower() == YES, message.chat.id))
        con_user.commit()
        if message.text.lower() == YES:
            my_send_message(message.chat.id,
                            'Введите время, в которое вы хотите получать расписане в формате HH:MM по времени MSK',
                            reply_markup=telebot.types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, set_timetable_time)
        elif set_all:
            end_of_start(message)
        elif is_reset:
            reset_timetable(message)


def set_timetable_time(message):
    global set_all
    global is_reset
    if len(message.text) != 5 or message.text[2] != ':' or \
            not message.text[0:2].isdigit() or not message.text[3:].isdigit():
        my_send_message(message.chat.id, 'Соблюдайте формат HH:MM')
        bot.register_next_step_handler(message, set_timetable_time)
    else:
        h = int(message.text[0:2])
        m = int(message.text[3:])
        if h < 0 or h >= 24 or m < 0 or m >= 60:
            my_send_message(message.chat.id, 'Соблюдайте формат HH:MM')
            bot.register_next_step_handler(message, set_timetable_time)
        else:
            con_user.execute("""UPDATE user SET timetable_h = ?, timetable_m = ? WHERE id = ?""",
                             (h, m, message.chat.id))
            con_user.commit()
            if set_all:
                end_of_start(message)
            elif is_reset:
                reset_timetable(message)


def end_of_start(message):
    global set_all
    my_send_message(message.chat.id, 'Теперь всё настроено! Вы можете нажать /help и узнать о моих командах.',
                    reply_markup=telebot.types.ReplyKeyboardRemove())
    print_settings(message)
    con_user.cursor().execute("""UPDATE user SET is_on = ? WHERE id = ?""", (1, message.chat.id))
    con_user.commit()
    add_user(message.chat.id)
    set_all = False


def print_settings(message):
    if not have_user(message):
        my_send_message(message.chat.id, 'Вы ещё не настроили бота! Для настройки нажмите /start')
    else:
        cur_user = get_info_user(message.chat.id)
        info = 'Ваша группа - ' + cur_user[1] + '.\n'
        info += 'За ' + str(cur_user[3]) + ' минут до начала лекции вам будет приходить уведомление о её начале.\n'
        if cur_user[4]:
            info += 'В ' + to_norm_format(cur_user[5]) + ":" + to_norm_format(
                cur_user[6]) + " вам будет приходить расписание на день."
        else:
            info += 'Вы не хотите, чтобы вам приходило уведомление о расписании.'
        my_send_message(message.chat.id, info)


@bot.message_handler(commands=['help'])
def help_message(message):
    my_send_message(message.chat.id, ("Привет, у меня есть несколько команд, чтобы я хорошо работал!\n"
                                      "/start - первая настройка бота.\n"
                                      "/time - изменить время, за которое до лекции придёт уведомление.\n"
                                      "/group - изменить группу.\n"
                                      "/timetable - отсутствие/наличие уведомления о расписании на день.\n"
                                      "/settings - покажет ваши текущие настройки.\n"
                                      "/on - включить бота, если он выключен.\n"
                                      "/off - выключить бота, если он включен.\n"
                                      "/today - расписание пар на сегодня.\n"
                                      "/tomorrow - расписание пар на завтра.\n"))


@bot.message_handler(commands=['start'])
def start_message(message):
    global set_all
    if have_user(message):
        my_send_message(message.chat.id,
                        'У вас уже есть сохранённые данные. Вы уверены, что хотите степерь их и настроить всё заново?',
                        reply_markup=keyboard_yesno)
        bot.register_next_step_handler(message, try_clear_data)
    else:
        set_all = True
        register_id(message)


@bot.message_handler(commands=['settings'])
def get_settings(message):
    print_settings(message)


@bot.message_handler(commands=['time'])
def reset_time(message):
    global is_reset
    if not have_user(message):
        my_send_message(message.chat.id, 'Вы ещё не настроили бота! Нажмите /start для настройки.')
    else:
        if not is_reset:
            is_reset = True
            my_send_message(message.chat.id,
                            'За сколько минут до начала лекции вы хотите, чтобы вам приходило уведомление?')
            bot.register_next_step_handler(message, set_time)
        else:
            my_send_message(message.chat.id,
                            'Теперь вам будут приходить уведомления за ' + str(get_user_time(message.chat.id)) +
                            ' минут до начала пары')
            is_reset = False


@bot.message_handler(commands=['group'])
def reset_group(message):
    global is_reset
    if not have_user(message):
        my_send_message(message.chat.id, 'Вы ещё не настроили бота! Нажмите /start для настройки.')
    else:
        if not is_reset:
            is_reset = True
            my_send_message(message.chat.id,
                            'Введите номер группы в стандартном формате. Например, БПМИ191 или БПИ195.')
            bot.register_next_step_handler(message, set_group)
        else:
            my_send_message(message.chat.id, "Теперь ваша группа " + str(get_user_group_label(message.chat.id)))
            is_reset = False


@bot.message_handler(commands=['timetable'])
def reset_timetable(message):
    global is_reset
    if not have_user(message):
        my_send_message(message.chat.id, 'Вы ещё не настроили бота! Нажмите /start для настройки.')
    else:
        if not is_reset:
            is_reset = True
            my_send_message(message.chat.id, 'Хотите получать уведомления о расписании?', reply_markup=keyboard_yesno)
            bot.register_next_step_handler(message, set_timetable)
        else:
            info = ''
            if get_user_timetable(message.chat.id):
                info += 'В ' + to_norm_format(get_user_timetable_h(message.chat.id)) + ":" + \
                        to_norm_format(
                            get_user_timetable_m(message.chat.id)) + " вам будет приходить расписание на день."
            else:
                info += 'Вы не хотите, чтобы вам приходило уведомление о расписании.'
            my_send_message(message.chat.id, info, reply_markup=telebot.types.ReplyKeyboardRemove())
            is_reset = False


@bot.message_handler(commands=['on'])
def set_on(message):
    if not have_user(message):
        my_send_message(message.chat.id, 'Вы ещё не настроили бота! Нажмите /start для настройки.')
    elif is_on(message):
        my_send_message(message.chat.id, 'Бот уже включен.')
    else:
        con_user.cursor().execute("""UPDATE user SET is_on = ? WHERE id = ?""", (1, message.chat.id))
        con_user.commit()
        my_send_message(message.chat.id, 'Вы включили бота.')


@bot.message_handler(commands=['off'])
def set_off(message):
    if not have_user(message):
        my_send_message(message.chat.id, 'Вы ещё не настроили бота! Нажмите /start для настройки.')
    elif not is_on(message):
        my_send_message(message.chat.id, 'Бот уже выключен.')
    else:
        con_user.cursor().execute("""UPDATE user SET is_on = ? WHERE id = ?""", (0, message.chat.id))
        con_user.commit()
        my_send_message(message.chat.id, 'Вы выключили бота.')


def get_str_timetable(lessons):
    timetable = ""
    for lesson in lessons:
        timetable += "<b>" + str(lesson['discipline']) + "</b>, " + str(lesson['kindOfWork']).lower() + '\n'
        timetable += "Начало: " + str(lesson['beginLesson']) + '\n'
        timetable += "Преподаватель: " + str(lesson['lecturer']) + '\n'
        timetable += '\n'
    return timetable


def print_today_timetable(user_id):
    group_id = get_user_group_id(user_id)
    needed_date = get_str_date(datetime.datetime.today())
    data = json.loads(get_timetable_from_ruz(group_id, needed_date, needed_date))
    if len(data) > 0:
        timetable = "<b>Расписание на сегодня:</b>\n\n" + get_str_timetable(data)
        my_send_message(user_id, timetable, parse_mode="html")
    else:
        my_send_message(user_id, "Сегодня чилл!")


@bot.message_handler(commands=['today'])
def today_timetable(message):
    print_today_timetable(message.chat.id)


@bot.message_handler(commands=['tomorrow'])
def tomorrow_timetable(message):
    user_id = message.chat.id
    group_id = get_user_group_id(user_id)
    needed_date = get_str_date(datetime.datetime.today() + datetime.timedelta(days=1))
    data = json.loads(get_timetable_from_ruz(group_id, needed_date, needed_date))
    if len(data) > 0:
        timetable = "<b>Расписание на завтра:</b>\n\n" + get_str_timetable(data)
        my_send_message(user_id, timetable, parse_mode="html")
    else:
        my_send_message(user_id, "Завтра чилл!")


#@bot.message_handler(content_types=['text'])
#def send_text(message):
#    my_send_message(message.chat.id, 'Чтобы узнать, что я умею, напиши /help')


def find_lesson(timetable, time):
    need_time = str(time.hour) + ":" + str(time.minute)
    for lesson in timetable:
        if lesson['beginLesson'] == need_time:
            return lesson


def print_time():
    print('TIME:\n')
    cur_cursor = con_time.cursor()
    cur_cursor.execute("""SELECT * FROM time""")
    print(cur_cursor.fetchall())


def print_ruz():
    print('RUZ:\n')
    cur_cursor = con_ruz.cursor()
    cur_cursor.execute("""SELECT * FROM ruz""")
    print(cur_cursor.fetchall())


def print_user():
    print('USER:\n')
    cur_cursor = con_user.cursor()
    cur_cursor.execute("""SELECT * FROM user""")
    print(cur_cursor.fetchall())


def go_poling():
    while True:
        try:
            bot.polling(none_stop=True, interval=0)
        except:
            print("Сраный прокси, каждый час вылетает")
            time.sleep(5)


def stupid_mistake():
    users = []
    for chat_id in users:
        my_send_message(chat_id,
                        'Я сломал свою базу данных со всеми настройками и уменя не было бекапа, поэтому если хотите, чтобы вам приходили уведомления, то перепройдите регистрацию, нажав на /start')

def print_lesson(user_id, lesson):
    try:
        msg = str(lesson['beginLesson']) + '\n' + "<b>" + str(lesson['discipline']) + "</b>" + '\n' + str(lesson['kindOfWork']) + \
          '\nПреподавталь: ' + str(lesson['lecturer']) + '\nСсылка: ' + str(lesson['url1'])
        my_send_message(user_id, msg, disable_web_page_preview=True, parse_mode="html")
    except:
        print('WTF?')
        print(user_id)
        print(lesson)


is_mistake = False
if is_mistake:
    stupid_mistake()
polling_thread = threading.Thread(target=go_poling)
polling_thread.start()
update_db()
print_time()
print_ruz()
print_user()
while 1:
    cur_date = datetime.datetime.now()
    cur_time = cur_date.time()
    if cur_time.minute == 0:
        update_db()
        print('Я обновил базы!')
    cursor = con_time.cursor()
    cursor.execute("""SELECT * FROM time WHERE h = ? AND m = ?""", (cur_time.hour, cur_time.minute))
    all_events = cursor.fetchall()
    for cur_event in all_events:
        user_id = cur_event[0]
        cursor = con_user.cursor()
        cursor.execute("""SELECT * FROM user WHERE id = ?""", (user_id,))
        cur_user = cursor.fetchall()[0]
        group_id = cur_user[2]
        if not cur_user[7]:
            continue
        cursor = con_ruz.cursor()
        cursor.execute("""SELECT * FROM ruz WHERE id = ?""", (group_id,))
        data = json.loads(cursor.fetchall()[0][1])
        if cur_event[3] == 'timetable':
            if len(data) > 0:
                timetable = "Расписание на сегодня:\n\n" + get_str_timetable(data)
                my_send_message(user_id, timetable, parse_mode="html")
        else:
            lesson = find_lesson(data, cur_date + datetime.timedelta(minutes=cur_user[3]))
            print_lesson(user_id, lesson)
    time.sleep(60)
