# -*- coding: utf-8 -*-
__author__ = 'Prostakov Alexey'
'''Программа толкает ТИ, чтобы она отправляла запросы.
Можно задать время с и по , когда программа работает,
и период толкания. Запускать программу нужно по расписанию,
т.к. по истечению периода она завершает работу'''
import time
import http.client
from xml.dom.minidom import *
import sys
import logging
import os

start_time = 8 # в часах
stop_time = 18 # в часах
period = 10 # в минутах
log_file = r'logs/ping.log'

# проверяем, чтобы была папка для логов
if os.access(r'logs/', os.F_OK) == False:
    # если ее нет, создаем
    os.mkdir('logs')

adr = r'192.168.0.3' # адрес точки интеграции
port = '2121' # порт
# если каталога для архива нет, создаем

def ping():
    '''Отправляет запрос на ТИ, чтобы заставить ее активировать очередь СМЭВ запросов,
    возвращает 0 - если хорошо или 1 если ошибка'''
    request = '''<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:soc="http://socit.ru/">
    <soapenv:Header/>
        <soapenv:Body>
            <soc:SendSmevRequest/>
        </soapenv:Body>
    </soapenv:Envelope>
    '''
    err = 0
    # соединяется с веб-сервисом
    con = http.client.HTTPConnection(adr, port)
    # пытаемся отправить 1-ю часть и получить guid
    headers = {"Content-Type": "text/xml; charset=utf-8",
               "SOAPAction": r"http://socit.ru/SendSmevRequest"}
    try:
        con.request("POST", "/socportal/export.asmx", request.encode('utf-8'), headers=headers)
        result = con.getresponse().read()
        result = result.decode('utf-8')
    except:
        Type, Value, Trace = sys.exc_info()
        logging.error("Не удалось обратится к методу SendSmevRequest, возникли ошибки. \
        Тип: %s Значение: %s" % (Type, Value))
        err += 1
    if err == 0:
        try:
            status = parseString(result).getElementsByTagName('HasError')[0].firstChild.nodeValue
        except:
            logging.error("Не удалось разобрать ответ веб-сервиса, возникли ошибки")
            logging.debug("Ответ сервиса: \n %s" % result)
            err += 1
            status = 'error'
        if status == 'false':
            logging.info("Выполнено успешно")
    return err


if __name__ == '__main__':
    logging.basicConfig(filename=log_file, filemode='a', level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
    logging.info("Пингатор запущен")
    logging.shutdown()
    while True:
        now = time.localtime()[3] # возвращает часы
        if (now>=start_time) and (now<=stop_time):
            logging.basicConfig(filename=log_file, filemode='a', level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
            # пока час в установленных пределах, работает вызываем функцию пингатор
            ping()
            # скидываем в файл каждое изменение и закрываем
            logging.shutdown()
            time.sleep(period*60)
