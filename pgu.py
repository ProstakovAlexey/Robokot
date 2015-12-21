# -*- coding: utf-8 -*-
__author__ = 'Prostakov Alexey'
import pypyodbc
import sys
import time, datetime
import smtplib
from email.mime.text import MIMEText
import os
import configparser
import logging
import http.client
from xml.dom.minidom import *

logging.basicConfig(filename='logs/pgu.log', filemode='a', level=logging.INFO,
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
    :return: словарь и список словарей (районы) кол-во ошибок
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
        raions = list()
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
                    raion = dict()
                    raion['name'] = name
                    raion['email'] = i.get('email', fallback=None)
                    raion['dbname'] = i.get('dbname', fallback=None)
                    raion['serveriis'] = i.get('serveriis', fallback=None)
                    raion['serverbd'] = i.get('serverbd', fallback=None)
                    raion['userId'] = i.get('userId', fallback=None)
                    # добавить район в список
                    raions.append(raion)
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


def last_zaiv(cur, d=0):
    '''Послучить информацию о последних заявления
    cur - курсор для БД
    d = 0 - за вчера,
    d = 1 - за 2 последних дня
    d = 2 - за 3 последних дня и т.д.
    '''
    sql_str = '''SELECT [requestId]
      ,[lastName]
      ,[firstName]
      ,[middleName]
      ,[requestDate]
      FROM [dbo].[EService_Request] WHERE DATEDIFF(dd,[requestDate], DATEADD(day,-1,GETDATE())) <= %s''' %d
    cur.execute (sql_str)
    # создаем список зявлений
    list_zaiv = list()
    for i in cur.fetchall():
        # в i - запись об очередном заявлении
        # создаем словарь, в нем информация о заявлении
        dict_zail = dict()
        dict_zail['id'] = i[0]
        dict_zail['famil'] = i[1]
        dict_zail['name'] = i[2]
        dict_zail['othc'] = i[3]
        dict_zail['date'] = i[4]
        list_zaiv.append(dict_zail)
    return list_zaiv


def print_zaiv(zaiv_list):
    '''
    :param zaiv_list: список заявлений для печати
    :return: строку с результатом
    '''
    result = ""
    if len(zaiv_list) >0:
        result += "Были приняты заявления в кол-ве %s шт.\n" % len(zaiv_list)
        result +="***************************************** \n"
        for i in zaiv_list:
            result += "Дата: %s \n" % i['date']
            result += "Номер: %s \n" % i['id']
            result += "Заявитель: %s %s %s\n" % (i['famil'], i['name'], i['othc'])
            result += "__________________________ \n"
    else:
        result += "Новых заявлений нет\n"
    return result


def print_big_zaiv(zaiv):
    '''
    :param zaiv: словарь с заявлениями. Ключ - название района, значение список
    0 - приняты
    1 - просрочены
    2 - не загружены в АСП
    :return: строка с результатом
    '''
    result = ""
    if zaiv :
        # словарь не пустой
        result += '-------------------------------------------------------------------------------------------------\n'
        for key in zaiv.keys():
            info = zaiv[key]
            result += "Район:%s, приняты:%s, не загружены в АСП:%s \n" %(key, info[0], info[2])
            result += "----------------------------------------------------------------------------------------------\n"
        result += "\n"
    return result


def report(text, const):
    msg = time.strftime('Date %Y.%m.%d, time %H:%M')+'\n'
    msg += text
    msg += "\n------\nАвтоматическое сообщение от РобоКот"
    msg_email = MIMEText(msg)
    msg_email['Subject'] = const['subject']
    msg_email['From'] = const['from']
    msg_email['To'] = const['to']
    if 'cc' in const:
        # если определен ключ с копией, то добавим ее
        msg_email['CC'] = const['cc']
    logging.debug("""Подготовили к отправке письмо
    ******************************************
    Кому: %s
    От кого: %s
    Тема: %s
    Тело: %s
    """ % (msg_email['To'], msg_email['From'], msg_email['Subject'], msg))
    try:
        s = smtplib.SMTP_SSL(const['smtp'])
        # Если нужно поменяйте логин и пароль на свой
        s.login(const['login'], const['passw'])
        # отправка сообщения
        s.send_message(msg_email)
        s.quit()
        logging.info("Сообщение на %s отправлено" % msg_email['To'])
    except:
        Type, Value, Trace = sys.exc_info()
        logging.error("""Возникла ошибка при отправке сообщения
        Сервер: %s, логин:%s пароль:%s
        Тип ошибки: %s
        Текст: %s""" %(const['smtp'], const['login'], const['passw'], Type, Value))


def all_zaiv(start, stop):
    """
    :param start: дата начала периода
    :param stop: дата окончания периода
    :return:
    """
    sql_str = """declare @param1_1 datetime, @param1_2 datetime
set @param1_1 = '%s'
set @param1_2 = '%s'
select ISNULL(u.name, 'Район не указан'), COUNT(*), SUM( CASE WHEN resp.state is not null and resp.state not in (1,2) THEN 1 ELSE 0 END )
 ,SUM( CASE WHEN resp.state = 4 THEN 1 ELSE 0 END )
 ,SUM( CASE WHEN resp.state = 3 THEN 1 ELSE 0 END )
 ,SUM( CASE WHEN resp.state is not null and resp.state not in (1,2,3,4) THEN 1 ELSE 0 END )
 ,SUM(
  CASE
   WHEN resp.state is not null and Datediff(d,r.requestDate,resp.date_Response) > 5 -- ответ дан позже чем положено
     or resp.state is null and Datediff(d,r.requestDate,GETDATE()) > 5 --срок ответа прошел
   THEN 1 ELSE 0
  END)
 ,SUM( CASE WHEN r.exportDate is null THEN 1 ELSE 0 END )
from EService_Request r
left join EService_Users u on u.id = r.EService_Users_id
--left join EService_Response resp on resp.eService_Request_id = r.id
OUTER  APPLY
    ( -- Последний статус последнего ответа
  SELECT TOP 1 resp.[state], resp.date_Response
  FROM  EService_Response resp
  WHERE resp.eService_Request_id = r.id and resp.[state] not in (1,2)
  order by resp.id desc
     ) resp
where r.requestDate between @param1_1 and Dateadd(SECOND, -1, Dateadd(DAY, 1, @param1_2))
group by u.name
order by u.name
""" % (start, stop)
    cur.execute(sql_str)
    # создаем словарь заявлений, ключ - имя района
    dict_zaiv = dict()
    for i in cur.fetchall():
        dict_zaiv[i[0]] = (i[1], i[6], i[7])
    return dict_zaiv


def AddNotification(raion, msg):
    """
    :param: raion - словарь данных о районе
    raion['dbname'] = имя базы данных с пользователем
    raion['serveriss'] = куда слать запрос
    raion['serverbd'] = где лежит база
    raion['userId'] = ИД пользователя
    :param: msg - сообщение
    :return: кол-во ошибок
    """
    err = 0
    if (raion['dbname'] is not None) and (raion['serveriis'] is not None) and \
            (raion['serverbd'] is not None) and (raion['userId'] is not None):
        # обязательные поля не пустые
        request = '''<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:soc="http://www.socit.ru/">
   <soapenv:Header/>
   <soapenv:Body>
      <soc:AddNotification>
         <soc:dbName>%s</soc:dbName>
         <soc:serverName>%s</soc:serverName>
         <soc:userId>%s</soc:userId>
         <soc:text>%s</soc:text>
      </soc:AddNotification>
   </soapenv:Body>
</soapenv:Envelope>
    ''' % (raion['dbname'], raion['serverbd'], raion['userId'], msg)
        # соединяется с веб-сервисом
        con = http.client.HTTPConnection(raion['serveriis'], 80)
        # пытаемся отправить запрос
        headers = {"Content-Type": "text/xml; charset=utf-8",
                   "SOAPAction": r"http://www.socit.ru/AddNotification"}
        try:
            # вот этот адрес можно переписать, в зависимости от того, как АСП установлена
            con.request("POST", "/ASPnet/WebService/transfer.asmx", request.encode('utf-8'), headers=headers)
            result = con.getresponse().read()
            result = result.decode('utf-8')
        except:
            # не удалось получить ответ от сервиса
            Type, Value, Trace = sys.exc_info()
            logging.error("Не удалось обратится к методу AddNotification, возникли ошибки. \
            Тип: %s Значение: %s" % (Type, Value))
            err += 1
        if err == 0:
            try:
                status = parseString(result).getElementsByTagName('HasError')[0].firstChild.nodeValue
            except:
                # ответ пришел, но в нем нет HasError, вероятно сервис развалился
                logging.error("Не удалось разобрать ответ веб-сервиса, возникли ошибки")
                logging.debug("Ответ сервиса: \n %s" % result)
                logging.debug("Запрос к сервису: \n %s" % request)
                status = 'True'
                err += 1
            if status == 'false':
                logging.info("Запись напоминания в БД %s выполнена успешно" % raion['dbname'])
            else:
                logging.error("Метод AddNotification вернул ошибку. Получено сообщение %s" % result)
                err +=1
    else:
        # нет обязательных данных для отправки запроса (см. словарь raion)
        logging.debug('Для района %s не хватате обязательных параметров для отправки уведомлений в АСП. \
        Сообщение не будет отправлено' % raion['name'])

    return err


if __name__ == '__main__':
    # Выполняется если файл запускается как программа
    logging.info("Запуск программы")
    # читаем конфиг
    const, raions, err = readConfig()
    # перенастраиваем стандартный вывод в файл

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
        # выходим из программы, если с БД не удалось соединится
        exit(1)
    else:
        logging.debug("Успешно соединились с БД")
        # получим информацию за текущий день и предидущий
        end = datetime.date.today().strftime('%Y%m%d')
        start = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y%m%d')
        zaiv = all_zaiv(start, end)
        str_res = print_big_zaiv(zaiv)
        result = last_zaiv(cur, 0)
        str_res += print_zaiv(result)
        cur.close()
        con.close()
    # уведомление администратору
    report(str_res, const)
    # контрольная печать в консоль
    #print ("Письмо администратору \n", str_res)

    # отправка индивидуальных email
    # определение констант для отправки в районы
    raion_const = dict()
    raion_const['subject'] = const['subject']
    raion_const['from'] = const['from']
    raion_const['smtp'] = const['smtp']
    raion_const['login'] = const['login']
    raion_const['passw'] = const['passw']
    # можно копию поставить
    #raion_const['cc'] = 'test@mail.ru'
    # перебираем словарь районов из конфига
    for raion in raions:
        key = raion['name']
        # если район есть в отчете, по будем пробовать уведомления выслать
        if (key in zaiv):
            info = zaiv[key]
            # если указан какой-то email будем слать
            if raion['email']:
                raion_const['to'] = raion['email']
                # шаблон письма в район
                text = """Район:%s
********************************************
приняты:%s
не загружены в АСП:%s""" %(key, info[0], info[2])
                report(text, raion_const)
            # если есть незагруженные заявления, то показать напоминание в АСП
            if info[2] > -1:
                # шаблон уведомления, можно применять html
                notification = "%s Есть заявления с ПГУ, не загруженные в АСП. Кол-во: %s" \
                               % (time.strftime('%d.%m.%Y %H:%M'), info[2])
                AddNotification(raion, notification)
    logging.info("программа закончила работу")