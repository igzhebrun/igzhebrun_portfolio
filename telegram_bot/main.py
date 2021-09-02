import config
import telebot
from telebot import types
import sqlite3
import requests  
from bs4 import BeautifulSoup
import time
from fake_useragent import UserAgent
import numpy as np
import pandas as pd
import ast
#import matplotlib
#matplotlib.use('Agg')
import matplotlib.pyplot as plt
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
opts = Options()
opts.add_argument(f"user-agent={UserAgent(verify_ssl=False).chrome}")

# подключим токен нашего бота
bot = telebot.TeleBot(config.token)
conn = sqlite3.connect('flats_hse.db')
cursor = conn.cursor()

# напишем, что делать нашему боту при команде старт
@bot.message_handler(commands=['start'])
def start(message, text="Привет, чтобы я начал работать, нужно спарсить Циан\nНажми кнопку"):
    keyboard = types.ReplyKeyboardMarkup()  # наша клавиатура
    itembtn1 = types.KeyboardButton('Just do it!') # создадим кнопку
    keyboard.add(itembtn1) # добавим кнопки
    # пришлем это все сообщением и запишем выбранный вариант
    msg = bot.send_message(message.from_user.id,
                     text=text, reply_markup=keyboard)

    # отправим этот вариант в функцию, которая его обработает
    bot.register_next_step_handler(msg, callback_worker)

def send_keyboard(message, text="Что хочешь посмотреть?"):
    keyboard = types.ReplyKeyboardMarkup()  # наша клавиатура
    itembtn1 = types.KeyboardButton('Топ риэлторов') # создадим кнопку
    itembtn2 = types.KeyboardButton('Топ квартир по цене и площади')
    itembtn3 = types.KeyboardButton('Распределение квартир по цене')
    itembtn4 = types.KeyboardButton('Обновить данные парсером')
    itembtn5 = types.KeyboardButton('Пока все!')
    keyboard.add(itembtn1)
    keyboard.add(itembtn2)
    keyboard.add(itembtn3)
    keyboard.add(itembtn4)
    keyboard.add(itembtn5) # добавим кнопки 

    # пришлем это все сообщением и запишем выбранный вариант
    msg = bot.send_message(message.from_user.id,
                     text=text, reply_markup=keyboard)

    # отправим этот вариант в функцию, которая его обработает
    bot.register_next_step_handler(msg, callback_worker)

def links_parser():
    driver = webdriver.Chrome(executable_path=r'C:\Users\ilja_\.wdm\drivers\chromedriver\win32\91.0.4472.101\chromedriver.exe', options=opts)
    
    path_head = 'https://nn.cian.ru/cat.php?deal_type=rent&engine_version=2&offer_type=flat&p='
    path_tail = '&region=4885&room1=1&room2=1&room3=1&room4=1&room5=1&room6=1&type=4'
    links = []
    for page in range(1,10): #страниц гораздо больше, но в этот раз мы используем малое количество для ускорения
        path = path_head + str(page) + path_tail
        driver.get(path)
        #time.sleep(0.5)
        #response = requests.get(path, headers={'User-Agent': UserAgent().chrome})
        tree = BeautifulSoup(driver.page_source, 'html.parser')
        linkareas = tree.find_all('div', {'data-name' : 'LinkArea'})
        for linkarea in linkareas:
            links.append(linkarea.find('a').get('href'))
    driver.close()
    return links

def new_flat(tree):
    flat = {}
    flat['rooms'] = int(tree.find_all('div', {'data-name' : 'OfferTitle'})[0].find('h1').text.split('.')[0].replace('-комн', ''))
    flat['price'] = int(tree.find_all('span', {'itemprop' : 'price'})[0].get('content').replace(' ₽/мес.', '').replace(' ', ''))
    try:
        dep, com, pre, _ =  tree.find_all('div', {'data-name' : 'OfferTerms'})[0].find('p').text.replace('\xa0', ' ').split(', ')
        flat['deposit'] = float(dep.replace('Без залога', '0').replace('₽', '').replace('Залог', '').replace(' ', ''))
        flat['comission'] = float(com.replace('без комиссии', '0').replace('%', '').replace('комиссия ', ''))
        flat['prepay'] = int(pre.replace('без предоплаты', '0').replace('предоплата за ', '').replace(' месяца', '').replace(' месяц', ''))
    except:
        pass
    try:    
        flat['total_area'] = float(tree.find_all('div', text='Общая')[0].find_previous('div').text.replace('\xa0', ' ').replace(' м²', '').replace(',', '.'))
    except:
        pass
    try:
        tmp = str(tree.find_all('script', {'type' : 'text/javascript'}))
        i1 = tmp.find('coordinates')
        i2 = tmp.find('}', i1)
        tmp_dict = ast.literal_eval(tmp[i1:i2+1].replace('coordinates":', ''))
        flat['lng'] = float(tmp_dict['lng'])
        flat['lat'] = float(tmp_dict['lat'])
    except:
        pass
    try:
        flat['tel'] = tree.find_all('div', {'data-name' : 'OfferContactsAside'})[0].find('a').get('href').replace('tel:', '')
    except:
        pass
    flat['address'] = tree.find_all('div', {'data-name' : 'Geo'})[0].find_all('span')[0].get('content')
    try:
        flat['description'] = tree.find_all('div', {'data-name' : 'Description'})[0].find('p').text
    except:
        pass
    return flat

def parser(links):
    driver = webdriver.Chrome(executable_path=r'C:\Users\ilja_\.wdm\drivers\chromedriver\win32\91.0.4472.101\chromedriver.exe', options=opts)
    
    
    flats_list = []
    for link in links:
        try:
            driver.get(link)
            html = driver.page_source
        except:
            continue
        tree = BeautifulSoup(html, 'html.parser')
        flat = new_flat(tree)
        flat['link'] = link
        flats_list.append(flat)
    #time.sleep(1)
    driver.close()
    return flats_list

def df_to_str(df):
    s = ''
    cols = df.columns
    for i, data in df.head().iterrows():
        s +=f'{i+1}) '
        for col in cols:
            s += f'{col}: {data[col]}\n'
        s += '\n'
    return s

def best_seller(df):
    df['comission_in_tr'] = df['comission'] * df['price'] / 1000
    result = df.groupby(['tel'], as_index = False)['comission_in_tr'].\
    sum().sort_values(by='comission_in_tr', ascending=False, ignore_index=True).head(5)
    return result

def best_flat(df, n=3, rooms=0, price=0, total_area=0, deposit=0, comission=0, prepay=0):
    """Функция принимает в качестве параметров датафрейм, n = количество итоговых результатов,
    и одноименные веса для каждого столбца. Результатом работы функции является таблица с n строками
    и колонками для ненулевых весов + link, tel, description.
    При отрицательном значении веса, значения будут соритроваться в порядке убывания,
    при положительном - в порядке возрастания.
    !ВАЖНО веса нужно нормировать. Результат работы при price=-1, living_area=1 и 
    price=-1, living_area=500 будет разный.
    (В первом варианте большую роль играет цена, во втором оптимальное соотношение)"""
    best_flats = 0
    cols = []
    if rooms != 0:
        best_flats += df.rooms * rooms
        cols.append('rooms')
    if  price != 0:
        best_flats += df.price * price
        cols.append('price')
    if total_area != 0:
        best_flats += df.total_area * total_area
        cols.append('total_area')
    if deposit != 0:
        best_flats += df.deposit * deposit
        cols.append('deposit')
    if comission != 0:
        best_flats += df.comission * comission
        cols.append('comission')
    if prepay != 0:
        best_flats += df.prepay * prepay
        cols.append('prepay')
    cols.append('link')
    cols.append('tel')
    cols.append('description')
    result = df.iloc[best_flats.sort_values(ascending=False).index].reset_index().iloc[:n][cols]
    return result

def flats_on_price(df) -> None:
    plot1 = df['price'].plot(kind='hist', figsize=(9,5))
    plot1 = plt.xlabel('цена')
    plot1 = plt.ylabel('количесттво квартир')
    plot1 = plt.title('Распределение квартир по цене')
    plot1 = plt.savefig('f_on_p.png', bbox_inches='tight')
    
# привязываем функции к кнопкам на клавиатуре
def callback_worker(call):
    if call.text == "Just do it!":
        bot.send_animation(call.chat.id, 'https://media.giphy.com/media/UqZ4imFIoljlr5O2sM/giphy.gif')
        try:
            conn = sqlite3.connect('flats_hse.db')
            df = pd.read_sql_query('SELECT * FROM flats', conn)
            bot.send_message(call.chat.id, 'Кажется, мы уже спарсили Циан. Можно смотреть аналитику')
        except:
            bot.send_message(call.chat.id, 'Я уже начал парсить ссылки, не отключайся)')
            links = links_parser()
            bot.send_message(call.chat.id, 'Отлично! Ссылки готовы, теперь буду парсить квартиры. Это очень долго!')
            flats_list = parser(links)
            df = pd.DataFrame(flats_list)
            df.deposit.fillna(0, inplace=True)
            df.comission.fillna(0, inplace=True)
            df.prepay.fillna(1, inplace=True)
            df.to_sql('flats', con=sqlite3.connect('flats_hse.db'))
            bot.send_message(call.chat.id, 'Ураа! Мы сделали это! Теперь можно смотреть аналитику')
        send_keyboard(call)
    elif call.text == 'Топ риэлторов':
        df = pd.read_sql_query('SELECT * FROM flats', con=sqlite3.connect('flats_hse.db'))
        bot.send_message(call.chat.id, 'Сколько заработают риэлторы в тысячах рублей:')
        text = df_to_str(best_seller(df))
        bot.send_message(call.chat.id, text)
        send_keyboard(call)
    elif call.text == 'Топ квартир по цене и площади':
        df = pd.read_sql_query('SELECT * FROM flats', con=sqlite3.connect('flats_hse.db'))
        text = df_to_str(best_flat(df, price=-1, total_area=500))
        bot.send_message(call.chat.id, text)
        send_keyboard(call)
    elif call.text == 'Распределение квартир по цене':
        df = pd.read_sql_query('SELECT * FROM flats', con=sqlite3.connect('flats_hse.db'))
        flats_on_price(df)
        bot.send_photo(call.chat.id, photo=open('f_on_p.png', 'rb'))
        send_keyboard(call)
    elif call.text == 'Обновить данные парсером':
        bot.send_message(call.chat.id, 'Сейчас я удалю данные, чтобы их обновить нажми /start')
        try:
            conn = sqlite3.connect('flats_hse.db')
            cursor = conn.cursor()
            query = "DROP TABLE flats"
            cursor.execute(query)
        except:
            bot.send_message(call.chat.id, 'Похоже данные отсутствуют. Нажми /start для добавления')
    elif call.text == 'Пока все!':
        bot.send_message(call.chat.id, 'Пока! Захочешь продолжить - нажми /start')
    
@bot.message_handler(content_types=['text'])
def handle_docs_audio(message):
    send_keyboard(message, text="Я не понимаю :-( Выберите один из пунктов меню:")

bot.polling(none_stop=True)