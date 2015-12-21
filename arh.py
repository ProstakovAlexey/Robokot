# -*- coding: utf-8 -*-
__author__ = 'Prostakov Alexey'
import os
import sys
import time
import tarfile
import configparser
import datetime
import logging

logging.basicConfig(filename='logs/arh.log', filemode='a', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s: %(message)s')


def readConfig(file="arh_config.ini"):
    '''
    :param file: имя файла конфигурации
    :return: словарь, первый ключ - имя секции, значение - словарь с константами
    и кол-во ошибок
    '''
    if os.access(file, os.F_OK):
        # выполняется если найден конфигурационный файл
        config_str = open(file, encoding='utf-8', mode='r').read()
        # удалить признак кодировки
        config_str = config_str.replace(u'\ufeff', '')
        Config = configparser.ConfigParser()
        Config.read_string(config_str)
        sections = Config.sections()
        result = dict()
        err = 0
        for section in sections:
            const = dict()
            i = Config[section]
            const["xml_life"] = int(i.get('log_life', fallback=0))
            const["arh_life"] = int(i.get('arh_life', fallback=15))
            const["log"] = i.get('log_dir', fallback=None)
            const["arhive_log"] = i.get('arh_dir', fallback=None)
            if const["log"] == None :
                logging.critical("Ошибка! Не указана папка с логами")
                err +=1
            if const["arhive_log"] == None :
                logging.critical("Ошибка! Не указана папка для архива")
                err +=1
            result[str(i)] = const
    else:
        logging.critical("Ошибка! Не найден конфигурационный файл")
        result = None
        err = 1
    return result, err


def arh_log(xml_life, log, arhive_log, name="АС Соцпортал"):
    """Архивирует логи соцпортала возрастом больше указанного кол-ва дней. По умолчанию 5 дней.
     Коды возврата:
     0 - все ОК
     1 - нет каталога с логами
     2 - нет каталога куда класть архив.
     Обычно ошибки связаны с недоступностью сетевых дисков"""
    # Папка где лежат логи

    err = 0
    logging.debug("Архивация логов %s - Папка с логами: %s "
                  "Папка с архивом: %s Удаляю логи старше %s дней" % (name, log, arhive_log, xml_life))

    if os.access(log, os.F_OK) == False:
        logging.error("Каталог с логами не существует")
        err += 1
    if os.access(arhive_log, os.F_OK) == False:
        logging.error("Каталог для архива не существует")


    # выполняем дальше, только если ошибок не возникло
    if err == 0:
        # если каталога для архива нет, создаем
        if os.access(arhive_log, os.F_OK) == False:
            os.mkdir(arhive_log)
            logging.info("Каталог для архивов был создан: " + arhive_log)
        # кол-во секунд с начала эпохи старше которого файл будет удален
        delta = time.time() - (xml_life*24*60*60)

        # кол-во удаленных папок
        num_dir = 0
        num_file = 0
        # Составляю список файлов для архивации
        list_file = list()
        for (p, d, f) in os.walk(log, topdown='False'):
            # p - текущий каталог
            # f - файл
            for file_name in f:
                full_name = os.path.join(p, file_name)
                # возвращает кол-во сек. с начала эпохи прошедшие с создания файла
                if os.path.getctime(full_name)<delta:
                    # добавляем файлы в список
                    list_file.append(full_name)


        if len(list_file)>0 :
            # если список не пустой, то делаем архив
            # имя архива это дата, старше которой файлов нет
            arh_name = datetime.date.today() - datetime.timedelta(days=xml_life)
            arh_name = arh_name.strftime(arhive_log + "\%Y.%m.%d")+'.tar.xz' # полное имя
            # проверяем если такой файл
            n = 0 # используется для создания имени если файл есть
            while os.path.exists(arh_name):
                n +=1
                arh_name = datetime.date.today() - datetime.timedelta(days=xml_life)
                arh_name = arh_name.strftime(arhive_log + "\%Y.%m.%d")+('(%s).tar.xz' %n)
            try:
                mytar = tarfile.open(arh_name, mode='w|xz')  # делаем сжатый tar файл
                for i in list_file:
                    mytar.add(i)
                mytar.close()
            except:
                Type, Value, Trace = sys.exc_info()
                error = "Во время создания tar.xz архива произошли ошибки, XML файлы остались без изменений" \
                        "Тип ошибки: %s Текст: %s" % (Type, Value)
                logging.critical(error)
            else:
                # выполняем, если при создании архива не возникло ошибок
                logging.info("Был создан архив: %s" % arh_name)
                # удаляем заархивированные файлы
                for i in list_file:
                    os.remove(i)
                num_file = len(list_file)
        # удаляем пустые каталоги
        for (p, d, f) in os.walk(log, topdown='False'):
                # p - текущий каталог
                # f - файл
                for dir_name in d:
                    try:
                        os.rmdir(os.path.join(p, dir_name))
                    except WindowsError:
                        # не смог удалить папку
                        # формальное действие
                        num_dir += 0
                    else:
                        num_dir += 1
        logging.info("Было удалено - Файлов: %s  Папок: %s" % (num_file, num_dir))


def arh_del(arhive_log, arh_life):

    err = 0
    if os.access(arhive_log, os.F_OK) == False:
        logging.critical("Каталог для архива не существует")
        err +=5
    else:
        # чистим старые архивы, старше arh_life дней
        delta = time.time() - (arh_life*24*60*60)
        logging.debug("Очистка старых архивов. Папка с архивом: %s Удаляю архивы старше %s дней" % (arhive_log, arh_life))
        for (p, d, f) in os.walk(arhive_log, topdown='False'):
            # p - текущий каталог
            # f - файл
            for file_name in f:
                full_name = os.path.join(p, file_name)
                # возвращает кол-во сек. с начала эпохи
                if os.path.getmtime(full_name)<delta:
                    os.remove(full_name)
                    logging.debug("Удалил архив: " + full_name)
    return err

logging.info("Запуск программы архивации")
err = 0
# пробуем архивировать
config, err = readConfig("arhiv.ini")
if err == 0:
    for key in config.keys():
        sec = config[key]
        try:
            arh_log(xml_life=sec["xml_life"], log=sec["log"], arhive_log=sec["arhive_log"], name=key)
            arh_del(sec["arhive_log"], sec["arh_life"])
        except:
            # во время работы архивации произошли ошибки
            Type, Value, Trace = sys.exc_info()
            logging.critical("Во время архивирования произошла ошибка. Тип ошибки: %s Текст: %s" % (Type, Value))
            err += 1
logging.info("Остановка программы архивации")
exit(err)
