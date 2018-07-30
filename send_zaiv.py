import glob
from xml.dom.minidom import *
import smev
import os.path


"""
Программа предназначена для отправки сбойных заявлений.
1. Ей нужно указать папку, в которой лежат xml логи и список номеров заявлений.
2. Она пробежит по этой папке, найдет все запросы по SetRequest(.....), без resp.
3. Соберет список файлов к отправке. Напишет отчет, сколько найдено.
4. Выполнит отправку заявлений на метод SetRequest.
5. Во время отправки выполняется проверка, что отправка прошла успешно.
"""

# Папка с XML логами
log_path = r'd:\PGU_GosUsl'
# Список номеров заявлнений для отправки
number_list = ('1532508470349', '1532506230424', '1532505911913', '1532506792810',
               '1532436437398', '1532458793781', '1532452002076', '1530020836218',
               '1532435430709', '1532432227483', '1532419579349', '1532420088349',
               '1532417751965', '1532418039514', '1532417536757', '1532407921447',
               '1532407166436', '1532406550720', '1532406758455', '1532404945280',
               '1532268150081', '1532343012288', '1532326114048', '1532319954960',
               '1532319036945', '1532286543786', '1532283235492')

# Куда отправлять
IS = dict()
IS['url'] = '/socportal/'
IS['adr'] = 'tu'
IS['port'] = 2121


def send_zaivls(file_name):
    """
    Отправляет заявление
    :param file_name: имя файла с заявлением
    :return : список строк для записи в протокол
    """
    with open(file_name, 'r', encoding='utf-8') as fp:
        req = fp.read()
    # TODO надо сделать извлечение номера и статуса правильно, с учетом пространства имен и вложенности.
    # TODO Тоже самое и в модуле smev.py
    numer = parseString(req).getElementsByTagName('smev:CaseNumber')[0].firstChild.nodeValue
    resp = smev.pgu_send(IS, req, pre=numer, soapaction='SetRequest', url=r"/pgu/RequestAllowanceServiceSOAP256.ashx")
    error_code = 1
    try:
        if parseString(resp).getElementsByTagName('smev:Status')[0].firstChild.nodeValue == 'ACCEPT':
            error_code = 0
    except:
        pass
    if error_code:
        print('Ошибка при отправке заявления:', file_name)
    return error_code


# Составляю список для отправки
zaiv_list = list()
print('Ищу заявления для отправки')
for file_name in glob.glob(os.path.join(log_path, 'SetRequest_(*.xml')):
    if file_name.find('_resp.xml') == -1:
        # Это не ответ
        for number in number_list:
            if file_name.find(number)>1:
                # Это нужное заявление
                zaiv_list.append(file_name)
                break
print('Выполнил поиск.\nСписок найденных: {0}\nНашел заявлений: {1}, должен был найти: {2}'
      .format(zaiv_list, len(zaiv_list), len(number_list)))
answ = input('Отправлять? (y/n)')
if answ.upper() == 'Y':
    # Отправляю
    for file_name in zaiv_list:
        send_zaivls(file_name)
    print('Отправка закончена.')
else:
    print('Отправка отменена.')
