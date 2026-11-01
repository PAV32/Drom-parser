import requests
from bs4 import BeautifulSoup
import csv
import time

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU, ru, q=0.9'
}
base_url = "https://auto.drom.ru/region25/all/"
filename = 'cars_note_RF1.csv'

# ПРАВКА 1: Создаем файл и пишем заголовки ОДИН РАЗ перед циклом
with open(filename, 'w', newline='', encoding='utf-8-sig') as file:
    writer = csv.writer(file, delimiter=';')
    writer.writerow(['Title', 'Price', 'Description', 'Broken', 'Local', 'Link'])

for page in range(1, 2751):
    print(f'--- Parsing page {page} ---')

    # ПРАВКА 2: Правильный URL для 1-й страницы (без /page1/)
    if page == 1:
        url = base_url
    else:
        url = f'{base_url}page{page}/'

    try:
        # Добавил timeout=10, чтобы скрипт не завис навсегда, если сайт не отвечает
        response = requests.get(url, headers=headers, timeout=10)

        # ПРАВКА 5: Защита от бана
        if response.status_code in [403, 429]:
            print(f"⚠️ Бан на странице {page}! Ждем 60 секунд...")
            time.sleep(60)
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        cars = soup.find_all('div', attrs={"data-ftid": "bulls-list_bull"})

        if len(cars) == 0:
            print('First 500 symbols HTML:')
            print(response.text[:500])
            print("Not found - End of pages.")
            break

        print(f'Found cars: {len(cars)}')

        # Создаем список для ОДНОЙ страницы
        page_data = []

        for car in cars:
            try:
                price_tag = car.find('span', attrs={"data-ftid": "bull_price"})
                if price_tag:
                    price_raw = price_tag.text.strip()
                    # ПРАВКА 4: Убираем неразрывный пробел, обычный пробел и знак рубля
                    price_clean = price_raw.replace('\xa0', '').replace(' ', '').replace('₽', '')
                    try:
                        price = int(price_clean)
                    except ValueError:
                        price = 0
                else:
                    price = 0  # Лучше писать 0, а не 'Close', чтобы Pandas потом не ругался

                descriptio_tag = car.find('div', attrs={"data-ftid": "bull_subtitle"})
                descriptio = descriptio_tag.text.strip() if descriptio_tag else 'None'

                broken_tag = car.find('div', attrs={"data-ftid": "bull_label_broken"})
                broken = 'Требуется ремонт' if broken_tag else 'Не требует ремонта'

                local_tag = car.find('span', attrs={"data-ftid": "bull_location"})
                # ПРАВКА 3: Если локации нет, пишем "Неизвестно", а не "Не требует ремонта"
                local = local_tag.text.strip() if local_tag else 'Неизвестно'

                title_link_tag = car.find('a', attrs={'data-ftid': 'bull_title'})
                if title_link_tag:
                    link = title_link_tag.get('href')
                    title = title_link_tag.find('h3').text.strip()
                else:
                    link = "Ссылка не найдена"
                    title = "Без названия"

                page_data.append([title, price, descriptio, broken, local, link])

            except Exception as e:
                continue  # Если одна машина сломалась, идем к следующей

        # ПРАВКА 1 (продолжение): Дописываем данные страницы в файл сразу (режим 'a' - append)
        with open(filename, 'a', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file, delimiter=';')
            writer.writerows(page_data)

        time.sleep(3)  # Пауза, чтобы Дром не забанил

    except Exception as e:
        print(f'Error on page {page}: {e}')
        time.sleep(5)  # Если сеть моргнула, ждем 5 секунд и идем дальше

print("Парсинг полностью завершен!")