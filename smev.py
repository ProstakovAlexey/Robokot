# -*- coding: utf-8 -*-
__author__ = 'alexey'
import http.client
import time
import sys
import random
import urllib.request
from xml.dom.minidom import *
import configparser
import os, glob

def get_wsdl(IS, url, name='wsdl.wsdl'):
    '''Получает WSDL и пишет его в файл'''
    addr = 'http://%s:%s%s?wsdl' % (IS['adr'], IS['port'], url)
    err =0
    file_name = 'Результаты/'+name
    try:
        response = urllib.request.urlopen(addr)
    except urllib.error.HTTPError:
        print ('При получении WSDL возникли ошибки! Не удалось обратится по адресу:', addr)
        err += 1
    else:
        print('WSDL успешно получена по адресу:', addr)
        wsdl = response.read().decode('utf-8')
        # убираем двойной перевод строки
        wsdl = wsdl.replace('\r\n', '\n')
        open (file_name, mode="w", encoding="utf8").write(wsdl)

    return err

def snils(init=0):
    """ Функция генерирует СНИСЛ, начинающийся с 002 (чтобы легче было искать) остальные
    числа случайные, контрольное число вычисляется
    Страховой номер индивидуального лицевого счета страхового свидетельства обязательного пенсионного страхования(он же СНИЛС) проверяется на валидность контрольным числом. СНИЛС имеет вид: «XXX-XXX-XXX YY», где XXX-XXX-XXX — собственно номер, а YY — контрольное число. Алгоритм формирования контрольного числа СНИЛС таков:
    1) Проверка контрольного числа Страхового номера проводится только для номеров больше номера 001-001-998
    2) Контрольное число СНИЛС рассчитывается следующим образом:
    2.1) Каждая цифра СНИЛС умножается на номер своей позиции (позиции отсчитываются с конца)
    2.2) Полученные произведения суммируются
    2.3) Если сумма меньше 100, то контрольное число равно самой сумме
    2.4) Если сумма равна 100 или 101, то контрольное число равно 00
    2.5) Если сумма больше 101, то сумма делится по остатку на 101 и контрольное число определяется остатком от деления аналогично пунктам 2.3 и 2.4
    ПРИМЕР: Указан СНИЛС 112-233-445 95
    Проверяем правильность контрольного числа:
    цифры номера        1 1 2 2 3 3 4 4 5
    номер позиции       9 8 7 6 5 4 3 2 1
    Сумма = 1×9 + 1×8 + 2×7 + 2×6 + 3×5 + 3×4 + 4×3 + 4×2 + 5×1 = 95
    95 ÷ 101 = 0, остаток 95.
    Контрольное число 95 — указано верно """
    if init !=0:
        random.seed(init)
    # заполняем начальные числа СНИСЛ
    arr = [0, 0, 2]
    # res - переменная для результата
    res = ""
    contr = 0
    for i in range(3, 9):
        arr.append(random.randint(0, 9))
    for i in range(0, 9):
        contr += arr[i] * (9 - i)
        res += str(arr[i])
    if contr > 99:
        if contr == 100 or contr == 101:
            contr = 0
        else:
            contr %= 101
    if contr < 10:
        res += "0" + str(contr)
    else:
        res += str(contr)
    return res

def get_smev_date():
    """ Возвращает текущую дату, в формате СМЭВ """
    # возвращает текущее время в struct_time
    now = time.localtime()
    # форматирование к виду 2014-01-16T14:51:45.566+04:00
    return time.strftime ("%Y-%m-%dT%H:%M:%S+03:00", now)

def case_num(n=6, init=0):
    '''Возвращает случайный номер состоящий из n цифр'''
    if init != 0:
        random.seed(init)
    result =''
    for i in range(0, n):
        s = random.randint(0, 9)
        result += str(s)
    return result

def change(s, IS, SERVICE_CODE=None, CASE_NUM = case_num(), SNILS = snils()):
    """Проводит замены в строке, возвращает готовую
    s: входная строка
    IS: сведения об ИС Наименование, Мнемоника, ОКТМО (словарь)
    """

    if SERVICE_CODE == None:
        SERVICE_CODE = IS['servicecode']
    s = s.replace ('#DATE#', get_smev_date())
    s = s.replace ('#SND_NAME#', IS['name'])
    s = s.replace ('#SND_CODE#', IS['mnemonic'])
    s = s.replace ('#OKTMO#', IS['oktmo'])
    s = s.replace ('#SERVICE_CODE#', SERVICE_CODE)
    s = s.replace ('#CASE_NUM#', CASE_NUM)
    s = s.replace ('#SNILS#', SNILS)
    s = s.replace ('#VERSION#', 'rev120315')
    s = s.replace('#SERVICE_MNEMONIC#', 'TestMnemonic' )
    s = s.replace('#SERVICE_VERSION#', '2.10')
    return s

def write_file(s, metod, code=None):
    """ Записывает файл. Вход - имя строка для записи в файл и префикс"""
    err = 0

    try:
        file_name = parseString(s).getElementsByTagName('smev:Status')[0]
        file_name = file_name.firstChild.nodeValue
    except:
        try:
            file_name = parseString(s).getElementsByTagName('rev:Status')[0]
            file_name = file_name.firstChild.nodeValue
        except:
            Type, Value, Trace = sys.exc_info()
            file_name = "FAULT"
            print("Не удалось распарсить файл. Вероятно xml структура повреждена.\
Файл будет сохранен как %s, выполнение продолжено" %(file_name))
            print ("Ошибка Тип:", Type, "Значение:", Value)
            err +=1
    if code:
        file_name = 'Результаты/%s(%s)_%s.xml' % (metod, code, file_name)
    else:
        file_name = 'Результаты/'+metod+'_'+file_name+'.xml'
    # добавляем строку с кодировкой если ее нет
    if s.startswith('<?xml version="1.0" encoding="utf-8"?>') == False:
        s = '<?xml version="1.0" encoding="utf-8"?>\n'+s
    open (file_name, mode="w", encoding="utf-8").write(s)
    return err

def service_373(req, IS, name='373'):
    '''Получает ответ от 373 сервиса, подставляет текущую дату в
    исходный файл.
    req: строка запроса (обязательный,в нем меняется время, наименование ИС, КОД, ОКТМО)
    numer: (обязательный, номер для образования имени)
    IS: обязательный, словарь. Сведения об ИС
    ответ сервера в строке или None в случае ошибки
    '''

    # проводим замены
    s = change(req, IS)

    # сохранить запрос
    write_file(s, name)

    # соединяется с веб-сервисом
    con = http.client.HTTPConnection(IS['adr'], IS['port'])
    # пытаемся отправить 1-ю часть и получить guid
    headers = {"Content-Type": "text/xml; charset=utf-8",
               "SOAPAction": "Request"}
    try:
        con.request("POST", IS['url']+"SMEV/Child256.ashx", s.encode('utf-8'), headers=headers)
        result = con.getresponse().read()
        result = result.decode('utf-8')
    except:
        Type, Value, Trace = sys.exc_info()
        print ("Не удалось обратится к методу Request " \
              "(1-я часть запроса), возникли ошибки:")
        print ("Тип:", Type, "Значение:", Value)
        print ("Выполнение будет продолжено")
        result = None
    else:
        # проверим, нет ли ошибки в 1-й части
        write_file(result, name)
        status = parseString(result).getElementsByTagName('smev:Status')[0].firstChild.nodeValue
        if status == u"ACCEPT":
            # нашли что статус ACCEPT
            # получение guid
            # сохранить ответ

            for node in parseString(result).getElementsByTagName('smev:RequestIdRef'):
                guid = node.childNodes[0].nodeValue
            #guid = guid.encode('utf8')
            s = open(r"Шаблоны/373-Ping.xml", "r", encoding="utf8").read()
            # проводим замены
            s = change(s,IS)
            # и меняем GUID
            s = s.replace(r"#RequestIdRef#", guid)
            s = s.replace(r"#OriginRequestIdRef#", guid)

            # сохранить запрос
            write_file(s,name)

            # пытаемся отправить 2-ю часть
            headers = {"Content-Type": "text/xml; charset=utf-8",
               "SOAPAction": "Request"}
            try:
                con.request("POST", IS['url']+"SMEV/Child256.ashx", s.encode('utf-8'), headers=headers)
                result = con.getresponse().read()
                result = result.decode('utf-8')
            except:
                Type, Value, Trace = sys.exc_info()
                print ("Не удалось обратится к методу Request" \
                  " (2-я часть запроса), возникли ошибки:")
                print ("Тип:", Type, "Значение:", Value)
                print ("Выполнение будет продолжено")
                result = None
            else:
                # сохранить ответ
                write_file(result,name)
    # если не нашли статус ACCEPT, то сразу попадаем сюда
    return result

def service_409(req, IS, name='409'):
    '''Получает ответ от 409 сервиса, подставляет текущую дату в
    исходный файл.
    req: строка запроса (обязательный,в нем меняется время, наименование ИС, КОД, ОКТМО)
    numer: (обязательный, номер для образования имени)
    IS: обязательный, словарь. Наименование ИС, мнемоника, ОКТМО
    ответ сервера в строке или None в случае ошибки
    '''

    # проводим замены
    s = change(req, IS)

    # сохранить запрос
    write_file(s, name)

    # соединяется с веб-сервисом
    con = http.client.HTTPConnection(IS['adr'], IS['port'])
    #con = http.client.HTTPSConnection(IS['adr'], IS['port'])

    # пытаемся отправить 1-ю часть и получить guid
    headers = {"Content-Type": "text/xml; charset=utf-8",
               "SOAPAction": "http://sum-soc-help.skmv.rstyle.com/SumSocHelpService/SumSocHelpRequestMessage"}
    try:
        con.request("POST", IS['url']+"SMEV/SocPayments256.ashx", s.encode('utf-8'), headers=headers)
        result = con.getresponse().read()
        result = result.decode('utf-8')
    except:
        Type, Value, Trace = sys.exc_info()
        print("Не удалось обратится к методу Request (1-я часть запроса), возникли ошибки:")
        print("Тип:", Type, "Значение:", Value)
        print("Выполнение будет продолжено")
        result = None
    else:
        # проверим, нет ли ошибки в 1-й части
        write_file(result, name)
        status = parseString(result).getElementsByTagName('smev:Status')[0].firstChild.nodeValue
        if status == u"ACCEPT":
            # нашли что статус ACCEPT
            # получение guid
            # сохранить ответ

            for node in parseString(result).getElementsByTagName('smev:RequestIdRef'):
                guid = node.childNodes[0].nodeValue
            #guid = guid.encode('utf8')
            s = open(r"Шаблоны/409-Ping.xml", "r", encoding="utf8").read()
            # проводим замены
            s = change(s, IS)
            # и меняем GUID
            s = s.replace(r"#RequestIdRef#", guid)
            s = s.replace(r"#OriginRequestIdRef#", guid)

            # сохранить запрос
            write_file(s,name)

            # пытаемся отправить 2-ю часть
            headers = {"Content-Type": "text/xml; charset=utf-8",
               "SOAPAction": "http://sum-soc-help.skmv.rstyle.com/SumSocHelpService/SumSocHelpRequestDataMessage"}
               #"SOAPAction": "SumSocHelpRequestData"}
            try:
                con.request("POST", IS['url']+"SMEV/SocPayments256.ashx", s.encode('utf-8'), headers=headers)
                result = con.getresponse().read()
                result = result.decode('utf-8')
            except:
                Type, Value, Trace = sys.exc_info()
                print("Не удалось обратится к методу Request (2-я часть запроса), возникли ошибки:")
                print ("Тип:", Type, "Значение:", Value)
                print ("Выполнение будет продолжено")
                result = None
            else:
                # сохранить ответ
                write_file(result, name)
    # если не нашли статус ACCEPT, то сразу попадаем сюда
    return result

def print_res(result):
    for i in range(0, len(result)):
        for j in range(0, len(result[i])):
            print(result[i][j],)
        print()

def pgu_send(IS, req, pre='pgu', soapaction="GetSettings", url=r"pgu/RequestAllowanceServiceSOAP256.ashx"):
    '''Получает ответ от сервиса ПГУ
    req: строка запроса
    pre: необязательный, для образования имени
    adr: адрес сервиса (необяз., по умолчанию service_adr)
    port: порт (необяз., по умолчанию =service_port)
    ответ сервера в строке или None в случае ошибки'''

    url = IS['url']+url
    # сохранить запрос
    write_file(req, soapaction, pre)

    # соединяется с веб-сервисом
    con = http.client.HTTPConnection(IS['adr'], IS['port'])

    # пытаемся отправить 1-ю часть и получить guid
    headers = {"Content-Type": "text/xml; charset=utf-8",
               "SOAPAction": soapaction}
    try:
        con.request("POST", url, req.encode('utf-8'), headers=headers)
        result = con.getresponse().read()
        result = result.decode('utf-8')
        # Сохранить ответ
        write_file(result, soapaction, pre)
    except:
        Type, Value, Trace = sys.exc_info()
        print ("Не удалось обратится к методу %s возникли ошибки:" % soapaction)
        print ("Тип:", Type, "Значение:", Value)
        print ("Выполнение будет продолжено")
        result = None
    else:
        # проверим, нет ли ошибки в 1-й части
        if write_file(result, soapaction, pre)  > 0:
            result = None
    return result

def readConfig(file="docum.ini"):
    '''
    :param file: имя файла конфигурации
    :return: словарь, первый ключ - имя секции, значение - словарь с константами
    и кол-во ошибок
    '''
    IS = dict()
    err = 0
    if os.access(file, os.F_OK):
        # выполняется если найден конфигурационный файл
        config_str = open(file, encoding='utf-8', mode='r').read()
        # удалить признак кодировки
        config_str = config_str.replace(u'\ufeff', '')
        Config = configparser.ConfigParser()
        Config.read_string(config_str)
        sections = Config.sections()
        # пример заполнения сведений от ИС
        for section in sections:
            i = Config[section]
            IS['name'] = i.get('name', fallback='СОЦИНФОРМТЕХ')
            IS['mnemonic'] = i.get('mnemonic', fallback='SOCP01711')
            IS['oktmo'] = i.get('OKTMO', fallback='70000000')
            IS['url'] = i.get('URL', fallback ='/socportal/')
            IS['adr'] = i.get('address', fallback='localhost')
            IS['port'] = i.get('port', fallback='80')
            IS['servicecode'] = i.get('SERVICE_CODE', fallback='123456789')
            IS['dir'] = i.get('dir', fallback='Заявки')
    else:
        print("Ошибка! Не найден конфигурационный файл")
        err = 1
    return IS, err


def service_510(req, IS, name='510'):
    """Получает ответ от 510 сервиса
    req: строка запроса (обязательный,в нем меняется время, наименование ИС, КОД, ОКТМО)
    numer: (обязательный, номер для образования имени)
    IS: обязательный, словарь. Наименование ИС, мнемоника, ОКТМО
    ответ сервера в строке или None в случае ошибки
    """

    # проводим замены
    s = change(req, IS)

    # сохранить запрос
    write_file(s, name)

    # соединяется с веб-сервисом
    con = http.client.HTTPConnection(IS['adr'], IS['port'])

    # пытаемся отправить 1-ю часть и получить ответ
    headers = {"Content-Type": "text/xml; charset=utf-8",
               "SOAPAction": "queryLongServicePension"}
    try:
        con.request("POST", IS['url']+"/SMEV/GosPension256.ashx", s.encode('utf-8'), headers=headers)
        result = con.getresponse().read()
        result = result.decode('utf-8')
    except:
        Type, Value, Trace = sys.exc_info()
        print("Не удалось обратится к методу Request (1-я часть запроса), возникли ошибки:")
        print("Тип:", Type, "Значение:", Value)
        print("Выполнение будет продолжено")
        result = None
    else:
        # проверим, нет ли ошибки в 1-й части
        write_file(result, name)
    return result
