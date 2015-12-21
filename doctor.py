# -*- coding: utf-8 -*-
__author__ = 'Prostakov Alexey'
import pypyodbc
import sys
import os
import configparser
import logging

logging.basicConfig(filename='logs/doctor.log', filemode='a', level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s')
"""
Можно изменить подробность логирования
DEBUG 	Detailed information, typically of interest only when diagnosing problems.
INFO 	Confirmation that things are working as expected.
WARNING 	An indication that something unexpected happened, or indicative of some problem in the near future (e.g. ‘disk space low’). The software is still working as expected.
ERROR 	Due to a more serious problem, the software has not been able to perform some function.
CRITICAL 	A serious error, indicating that the program itself may be unable to continue running.
"""


def readConfig(file="pgu.ini"):
    '''
    :param file: имя файла конфигурации
    :return: два словаря и кол-во ошибок
    1. первый ключ - имя секции, значение - словарь с константами
    и кол-во ошибок
    2. ключ - название района, адрес почты для отправки
    '''
    err = 0
    if os.access(file, os.F_OK):
        # выполняется если найден конфигурационный файл
        config_str = open(file, encoding='utf-8', mode='r').read()
        # удалить признак кодировки
        config_str = config_str.replace(u'\ufeff', '')
        Config = configparser.ConfigParser()
        Config.read_string(config_str)
        logging.debug("Читаем конфигурационный файл")
        sections = Config.sections()
        const = dict()
        raions = dict()
        for section in sections:
            i = Config[section]
            # чтение настроек БД
            if section == 'DataBase':
                const["server"] = i.get('server', fallback=None)
                const["database"] = i.get('database', fallback=None)
                const["pwd"] = i.get('pwd', fallback='111')
                logging.debug("Прочитана секция с настройками БД")

            # чтение настроек для исходящего сообщения
            elif section == 'Mail':
                const["subject"] = i.get('subject', fallback="Новые заявления на ТИ")
                const['from'] = i.get('from', fallback="forum.socit@yandex.ru")
                const['to'] = i.get('to', fallback="inbox@socit.ru")
                copy = i.get('cc', fallback=None)
                if copy:
                    const['cc'] = copy
                logging.debug("Прочитана секция с настройками email")

            # чтение настроек для SMPT сервера
            elif section == 'SMTP':
                const['smtp'] = i.get('smtp', fallback="smtp.yandex.ru")
                const['login'] = i.get('login', fallback="forum.socit")
                const['passw'] = i.get('passw', fallback="pic45@UI")

            # чтение настроек для районов
            elif section.startswith('Район'):
                # проверяет, что строка начинается со слова Район
                name = i.get('name', fallback=None)
                if name:
                    # имя указано, можно дальше разбирать
                    raions[name] = i.get('email', fallback=None)
                else:
                    err += 1
                    print("Ошибка в конфигурации. Значение name для одного из районов не указано")
                logging.debug("Прочитана секция с настройками района: %s" % section)


        for key in const.keys():
            logging.debug("Констанка %s=%s" % (key, const[key]))
            if const[key] == None:
                # если нашли незаполненную константу, то ошибка
                err += 1
                logging.error("Ошибка в конфигурации. Значение для константы %s не указано" %key)
    else:
        print("Ошибка! Не найден конфигурационный файл")
        const = None
        err += 1
    return const, raions, err


def bad_pdu(cur):
    '''Выдает информацию о сломанных заявления с ПГУ
    '''
    sql_str = '''select COUNT(ID) FROM EService_Request
where id in
(select er.id from EService_Request er
left join EService_Response err on err.eService_Request_id=er.id
where er.exportDate is not null and err.id is null)'''
    cur.execute (sql_str)
    # прочитаем одно значение, скрипт должен вернуть одно
    i = cur.fetchone()
    return i[0]


def doctor_pgu(cur, num=30):
    '''
    :param cur: курсор к БД
    :param num: сколько заявление перезапустить
    :return: возвращает кол-во плохив заявлений после запуска
    '''
    # получить список всех районов на сервере
    cur.execute("SELECT id, name FROM EService_users")
    # сохранить и перебирать по одному
    res = cur.fetchall()
    for user in res:
        # перезапускает заданное кол-во заявлений для нужного района
        sql = r"""update EService_Request
set exportDate = null
where id in
(select top %s er.id from EService_Request er
left join EService_Response err on err.eService_Request_id=er.id
where er.exportDate is not null and err.id is null and er.eservice_users_id=%s)""" % (num, user[0])
        cur.execute(sql)
        # кол-во перезапущенных по данному району заявлений
        zaiv = cur.rowcount
        # если больше нуля - в отчет.
        if zaiv:
            logging.info("Для района %s перезапущено %s заявлений" % (user[1], zaiv))
    # вносим изменения в БД
    cur.commit()
    # вывод в лог результатов
    logging.info("Заявления были перезапущены. Осталось плохих - %s" % bad_pdu(cur))


def doctor_smev(cur):
    """
    :param cur: курсор к БД
    :return: записывает в лог
    """
    sql = """-- Улавливает ситуацию, когда по одному СМЭВ-запросу есть несколько записей в SMEV_QUERIES
-- Хорошо, когда возвращает пустую таблицу
with A as
(select smev_request_id, count(id) col
from smev_queries
group by smev_request_id )
select * from A
where col > 1
order by col"""
    cur.execute(sql)
    res = cur.fetchall()
    if res:
        for i in res:
            # если что-то нашли, пишем в лог
            logging.debug("Больной СМЭВ запрос %s, кол-во повторов %s" % (i[0], i[1]))
        logging.error("Общее кол-во больных СМЭВ запросов %s" % len(res))
    else:
        logging.info(" Все СМЭВ запросы здоровы")


if __name__ == '__main__':
    # прочитали конфиг
    logging.info("Запуск программы Робокот-доктор")
    const, raions, err = readConfig()
    try:
        """Строка соединения взята отсюда http://stackoverflow.com/questions/17411362/connecting-python-3-3-to-microsoft-sql-server-2008
        еще надо скачать клиента http://www.sqlservercentral.com/Forums/Topic1458276-2799-1.aspx"""
        con = pypyodbc.connect('DRIVER={SQL Server Native Client 11.0}; SERVER=%s; DATABASE=%s; UID=sa; PWD=%s'
                               %(const['server'], const['database'], const['pwd']))
        cur = con.cursor()
    except pypyodbc.Error:
        Type, Value, Trace = sys.exc_info()
        error = """Возникла ошибка при соединении с БД. Работа программы прекращена, проверьте SQL сервер и настройки программы
        Тип ошибки: %s
        Текст: %s""" % (Type, Value)
        logging.critical(error)
        exit(1)
    logging.debug("Успешно соединились с БД")
    num = bad_pdu(cur)
    if (num > 0):
        logging.error("Кол-во больных заявлений с ПГУ - %s" %num)
        # если есть, то автоматом перезапустим
        doctor_pgu(cur, 10)
    else:
        logging.info("Больных заявлений с ПГУ нет")
    doctor_smev(cur)
    # закрываем соединение с БД
    con.close()
    logging.info("Программа Робокот-доктор закончила работу")