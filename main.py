import requests
import re
import time
import pandas as pd
from datetime import datetime
import os


def main():
    phone, pwd = authorization()
    while True:
        command = input('input command (add, delete, analytics, quit): ')
        if command == 'add':
            qr_string = input('input qr string: ')
            add(qr_string, phone, pwd)
        elif command == 'delete':
            delete()
        elif command == 'analytics':
            print('this command will appear very soon')
            analytics()
        elif command == 'quit':
            quit()
        else:
            print('your command is not found. try again:')


def add(qr_string, phone, pwd):
    dictonary = decode_qr(qr_string)
    t, s, fn, i, fp = dictonary['t'], dictonary['s'], dictonary['fn'], dictonary['i'], dictonary['fp']
    headers = {'Device-Id': '', 'Device-OS': ''}
    payload = {'fiscalSign': fp, 'date': t, 'sum': s}
    checkrequest(headers, payload, phone, pwd, fn, i)
    products = requestinfo(headers, phone, pwd, fn, i, fp)
    if have_duplicates(t):
        command = input('you have paycheck with the same date. you still want to add a paycheck? (y/n): ')
        if command == 'y':
            append_products_to_csv(products, t)
    else:
        append_products_to_csv(products, t)


def checkrequest(headers, payload, phone, pwd, fn, i):
    """Проверяет налчие чека. Печатает статус код - 204, если чек существует"""
    check_request = requests.get(
        'https://proverkacheka.nalog.ru:9999/v1/ofds/*/inns/*/fss/' + fn + '/operations/1/tickets/' + i, params=payload,
        headers=headers, auth=(phone, pwd))
    print('check request code', check_request.status_code)


def requestinfo(headers, phone, pwd, fn, i, fp):
    """Вовзращает список продуктов, упакованный в json"""
    request_info = requests.get(
            'https://proverkacheka.nalog.ru:9999/v1/inns/*/kkts/*/fss/' + fn + '/tickets/' + i + '?fiscalSign=' + fp + '&sendToEmail=no',
            headers=headers, auth=(phone, pwd))
    print('request status code', request_info.status_code)
    while request_info.status_code == 202:
        print('your paycheck currently under processing. please wait 1 min and do not stop running the program.')
        time.sleep(60)
        request_info = requests.get(
            'https://proverkacheka.nalog.ru:9999/v1/inns/*/kkts/*/fss/' + fn + '/tickets/' + i + '?fiscalSign=' + fp + '&sendToEmail=no',
            headers=headers, auth=(phone, pwd))
        print('request status code', request_info.status_code)
    return request_info.json()


def append_products_to_csv(products, t):
    """Добавляет список покупок из чека в products.csv"""
    my_products = pd.DataFrame(products['document']['receipt']['items'])
    my_products['price'] = my_products['price'] / 100
    my_products['sum'] = my_products['sum'] / 100
    datetime_check = datetime.strptime(t, '%Y%m%dT%H%M%S')
    my_products['datetime'] = datetime_check
    my_products['unix'] = time.mktime(datetime_check.timetuple())
    df = my_products[['datetime', 'unix', 'name', 'price', 'quantity', 'sum']]
    df.to_csv('products.csv', mode='a', header=os.stat("products.csv").st_size == 0)
    print('product list from this paycheck added to products.csv')


def decode_qr(qr_string):
    """Распаковывает информацию из qr-кода в чеке"""
    t = re.findall(r't=(\w+)', qr_string)[0]
    s = re.findall(r's=(\w+.\w+)', qr_string)[0].replace('.', '')
    fn = re.findall(r'fn=(\w+)', qr_string)[0]
    i = re.findall(r'i=(\w+)', qr_string)[0]
    fp = re.findall(r'fp=(\w+)', qr_string)[0]
    return {'t': t, 's': s, 'fn': fn, 'i': i, 'fp': fp}


def have_duplicates(t):
    """Вовзращает True в csv файле есть чек с таким же временем и False в обратном случе"""
    unix_time_paycheck = time.mktime(datetime.strptime(t, '%Y%m%dT%H%M%S').timetuple())
    df = pd.read_csv('products.csv', index_col=0)
    return len(df[df['unix'] == unix_time_paycheck]) != 0


def delete():
    """Удаляет из products.csv все элементы с указанной датой (список доступных для удаления дат выводится)"""
    df = pd.read_csv('products.csv', index_col=0)
    if len(list(df['datetime'].unique())) == 0:
        print("you don't have any items to delete")
        return
    print('you have paychecks with the specified dates: ')
    for i in list(df['datetime'].unique()):
        print(i)
    delete_paycheck = input('please, specify the date from the specified items to delete: ')
    df[df['datetime'] != delete_paycheck].to_csv('products.csv', mode='w', header=True)

    if len(df[df['datetime'] != delete_paycheck]) < len(df):
        print('delete is performed')
    else:
        print('deletion not executed')


def analytics():
    pass


def authorization():
    """Получение пары номер телефона/пароль для дальнейшего получения информации"""
    try:
        phone, pwd = read_saved_authorization_info('authorization.txt')
    except:
        phone, pwd = '', ''

    if phone != '' and pwd != '' and check_authorization(phone, pwd):
        use_saved_data = input('You have saved correct data for authorization (phone = '+phone+', password = '+pwd+').'
                                                                                    ' You want to use them? (y/n): ')
        if use_saved_data == 'y':
            return(phone, pwd)
        elif use_saved_data == 'n':
            command = input('you received phone/password pair from a text message from nalog.ru? (y/n): ')
            if command == 'y':
                phone = input('input your phone number (use format +7XXXYYYZZZZ): ')
                pwd = input('input your password from text message: ')
                if not check_authorization(phone, pwd):
                    print('Your pair phone/password is not correct. Please, try later.')
                    quit()
                offer_to_save_authorization_data(phone, pwd)
                return (phone, pwd)

            elif command == 'n':
                phone = pwd_request()
                pwd = input('input your password from text message: ')
                if not check_authorization(phone, pwd):
                    print('Your pair phone/password is not correct. Please, try later.')
                    quit()
                offer_to_save_authorization_data(phone, pwd)
                return (phone, pwd)
    else:
        print("You don't have saved correct data for authorization.")
        command = input('you received phone/password pair from a text message from nalog.ru? (y/n): ')
        if command == 'y':
            phone = input('input your phone number (use format +7XXXYYYZZZZ): ')
            pwd = input('input your password from text message: ')
            if not check_authorization(phone, pwd):
                print('Your pair phone/password is not correct. Please, try later.')
                quit()
            offer_to_save_authorization_data(phone, pwd)
            return (phone, pwd)

        elif command == 'n':
            phone = pwd_request()
            pwd = input('input your password from text message: ')
            if not check_authorization(phone, pwd):
                print('Your pair phone/password is not correct. Please, try later.')
                quit()
            offer_to_save_authorization_data(phone, pwd)
            return (phone, pwd)


def pwd_request():
    """
    Отправляет запрос на создание пароля для дальнейшего получения информации.
    Возвращает используемый номер телефона для дальнейшего использования
    """
    phone = input('input your phone number (use format +7XXXYYYZZZZ): ')
    r = requests.post('https://proverkacheka.nalog.ru:9999/v1/mobile/users/signup',
                      json={"email": "email@email.com", "name": "USERNAME", "phone": phone})
    print('Check your phone. You should have received your password via text MESSAGE.')


def offer_to_save_authorization_data(phone, pwd):
    can_save = input('you pair phone/password is correct. can you save their for future use? (y/n) ')
    if can_save == 'y':
        with open('authorization.txt', 'w') as f:
            f.write(phone + ' ' + pwd)



def check_authorization(phone, pwd):
    """
    Проверяет данные, указанные для авторизации. Возвращает True в случае корректных указанных данных и False
    в обратном случае.
    """
    headers = {'Device-Id': '', 'Device-OS': ''}
    fn, i, fp = '9285000100139783', '49792', '987741027'
    request_info = requests.get(
        'https://proverkacheka.nalog.ru:9999/v1/inns/*/kkts/*/fss/' + fn + '/tickets/' + i + '?fiscalSign=' + fp + '&sendToEmail=no',
        headers=headers, auth=(phone, pwd))
    return request_info.status_code == 200


def read_saved_authorization_info(path):
    """
    Пытается считать c файла информацию о сохраненных там паре phone/password
    """
    with open(path, 'r') as f:
        info = f.read().split()
        return (info[0], info[1])


if __name__ == '__main__':
    main()