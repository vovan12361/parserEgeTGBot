import base64
import time
import telebot
import pandas as pd
import os
from bs4 import BeautifulSoup as Bs
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from tabulate import tabulate

token = 'ENTER_TOKEN_HERE'
bot = telebot.TeleBot(token, threaded=False)

def pprint_df(dframe):
    return tabulate(dframe, headers='keys', showindex=False)

@bot.message_handler(commands=['start'])
def hello_user(message):
    bot.send_message(message.chat.id, f'Привет, {message.from_user.username}, введи /help!')

@bot.message_handler(commands=['help'])
def show_help(message):
    bot.send_message(message.chat.id,
                     'Введите /check <Фамилия> <Имя> <Отчество> <Код регистрации>.\nПример: "/check Попов Иван Максимович 611690964041"')

URL = "https://checkege.rustest.ru/"
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--no-sandbox')

@bot.message_handler(commands=['check'])
def check_result(message):
    def get_captcha_img():
        try:
            source_data = browser.page_source
            soup = Bs(source_data, 'html.parser')
            elem = str(soup.find('div', class_='captcha')).split('"')
            img_data = elem[5]
            print('[INFO] Successfully parsed base64 img')
            return img_data
        except Exception as ex:
            print('[ERROR] Exception on parsing base64 img:', ex)
            return None

    def convert_img(uid):
        try:
            img_data = get_captcha_img()
            if img_data:
                head, data = img_data.split(',', 1)
                file_ext = head.split(';')[0].split('/')[1]
                plain_data = base64.b64decode(data)
                file_path = f"{uid}.{file_ext}"
                with open(file_path, 'wb') as f:
                    f.write(plain_data)
                print('[INFO] Successfully converted base64 image to jpeg image!')
                return file_path
            return None
        except Exception as ex:
            print('[ERROR] Exception on converting image:', ex)
            return None

    def fillgaps(surname, name, patr, regcode, captcha):
        try:
            browser.find_element(By.ID, 'surname').send_keys(surname)
            browser.find_element(By.ID, 'name').send_keys(name)
            browser.find_element(By.ID, 'patr').send_keys(patr)
            if len(regcode) == 12:
                browser.find_element(By.ID, 'regNum').send_keys(regcode)
            elif len(regcode) == 6:
                browser.find_element(By.ID, 'passNum').send_keys(regcode)
            browser.find_element(By.ID, 'region_chosen').click()
            region_input = browser.find_element(By.XPATH, "//input[@tabindex='6']")
            region_input.send_keys('Кировская')
            region_input.send_keys(Keys.ENTER)
            browser.find_element(By.ID, 'captcha').send_keys(captcha)
        except Exception as ex:
            print('[ERROR] Exception on filling form:', ex)

    def come_captcha(message):
        global captcha
        captcha = message.text
        if len(captcha) != 6:
            bot.send_message(message.from_user.id, 'Вы неверно ввели каптчу. Ещё раз введите цифры с картинки.')
            bot.register_next_step_handler(message, come_captcha)
        else:
            bot.send_message(message.from_user.id, 'Вы ввели каптчу. Сейчас отправлю результаты ЕГЭ.')
            end_process()

    data = message.text.split(' ')
    uid = message.chat.id

    if len(data) != 5:
        bot.send_message(uid, 'Вы неверно ввели команду. Используйте /help')
        return

    surname, name, patr, regcode = data[1], data[2], data[3], data[4]

    if len(regcode) not in [6, 12]:
        bot.send_message(uid, 'Вы неверно ввели код регистрации или номер документа.')
        return

    bot.send_message(uid, 'Сейчас отправлю картинку. Введите код с картинки:')
    browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    browser.get(URL)
    time.sleep(0.2)
    photo_path = convert_img(uid)
    if photo_path:
        bot.send_photo(uid, photo=open(photo_path, 'rb'))
        os.remove(photo_path)
        bot.register_next_step_handler(message, come_captcha)

    def end_process():
        try:
            fillgaps(surname, name, patr, regcode, captcha)
            browser.find_element(By.ID, 'submit-btn').click()
            time.sleep(1)
            try:
                WebDriverWait(browser, 3).until(EC.presence_of_element_located((By.ID, 'table-container')))
                bot.send_message(uid, 'Страница загрузилась. Сейчас отправлю таблицу.')
                ds = pd.read_html(browser.page_source)[0]
                bot.send_message(chat_id=uid, text='<pre>' + pprint_df(ds) + '</pre>', parse_mode='HTML')
            except TimeoutException:
                bot.send_message(uid, 'Произошла ошибка при загрузке. Попробуйте ещё раз.')
        except Exception as ex:
            print('[ERROR] Exception on end process:', ex)
            bot.send_message(uid, 'Не удалось получить ответ с сервера. Проверьте правильность введенных данных. (/help)\n Попробуйте снова.')
        finally:
            browser.quit()

if __name__ == '__main__':
    bot.infinity_polling()
