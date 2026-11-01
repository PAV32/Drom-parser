import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import random
import io

# --- НАСТРОЙКА СТРАНИЦЫ ---
st.set_page_config(page_title="Парсер Drom.ru", page_icon="🚗", layout="wide")
st.title("🚗 Парсер объявлений Drom.ru")
st.write("Введите параметры, нажмите кнопку и скачайте готовый CSV файл.")

# --- БОКОВАЯ ПАНЕЛЬ (ВВОД ДАННЫХ) ---
with st.sidebar:
    st.header("Настройки парсинга")
    # Поле ввода для модели
    model_path = st.text_input("Модель (например: nissan/note)", value="nissan/note")
    # Ползунок для выбора количества страниц
    max_pages = st.slider("Количество страниц для парсинга", min_value=1, max_value=100, value=5)

    # Кнопка запуска
    start_btn = st.button("🚀 Начать парсинг", type="primary")

# --- ЛОГИКА ПАРСИНГА (СРАБАТЫВАЕТ ПО КНОПКЕ) ---
if start_btn:
    if not model_path:
        st.error("Введите модель!")
    else:
        # Создаем контейнеры для прогресс-бара и текста
        progress_bar = st.progress(0)
        status_text = st.empty()

        all_data = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
        }

        for page in range(1, max_pages + 1):
            # Обновляем текст статуса
            status_text.text(f"Парсим страницу {page} из {max_pages}...")

            if page == 1:
                url = f"https://auto.drom.ru/region25/{model_path}/all/"
            else:
                url = f"https://auto.drom.ru/region25/{model_path}/all/page{page}/"

            try:
                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code in [403, 429]:
                    st.warning(f"⚠️ Бан на странице {page}! Ждем 60 секунд...")
                    time.sleep(60)
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                cars = soup.find_all('div', attrs={"data-ftid": "bulls-list_bull"})

                if len(cars) == 0:
                    st.info(f"Объявления закончились на странице {page}.")
                    break

                for car in cars:
                    try:
                        # Парсинг цены
                        price_tag = car.find('span', attrs={"data-ftid": "bull_price"})
                        if price_tag:
                            price_clean = price_tag.text.strip().replace('\xa0', '').replace(' ', '').replace('₽', '')
                            try:
                                price = int(price_clean)
                            except ValueError:
                                price = 0
                        else:
                            price = 0

                        # Парсинг описания
                        desc_tag = car.find('div', attrs={"data-ftid": "bull_subtitle"})
                        description = desc_tag.text.strip() if desc_tag else 'None'

                        # Парсинг ремонта
                        broken_tag = car.find('div', attrs={"data-ftid": "bull_label_broken"})
                        broken = 'Требуется ремонт' if broken_tag else 'Не требует ремонта'

                        # Парсинг локации
                        local_tag = car.find('span', attrs={"data-ftid": "bull_location"})
                        local = local_tag.text.strip() if local_tag else 'Неизвестно'

                        # Парсинг названия и ссылки
                        title_link_tag = car.find('a', attrs={'data-ftid': 'bull_title'})
                        if title_link_tag:
                            link = title_link_tag.get('href')
                            title = title_link_tag.find('h3').text.strip()
                        else:
                            link, title = "Нет ссылки", "Без названия"

                        # Добавляем в список
                        all_data.append({
                            'Title': title,
                            'Price': price,
                            'Description': description,
                            'Broken': broken,
                            'Local': local,
                            'Link': link
                        })
                    except Exception:
                        continue

                # Обновляем прогресс-бар
                progress_bar.progress(page / max_pages)
                # Пауза
                time.sleep(random.uniform(1.5, 3.0))

            except Exception as e:
                st.error(f"Ошибка на странице {page}: {e}")
                time.sleep(5)

        # --- ВЫВОД РЕЗУЛЬТАТОВ ---
        status_text.text("✅ Парсинг завершен!")

        if all_data:
            # Превращаем список словарей в DataFrame
            df = pd.DataFrame(all_data)

            st.success(f"Успешно собрано {len(df)} машин!")

            # Показываем таблицу на сайте
            st.dataframe(df)

            # Кнопка для скачивания
            # Конвертируем DataFrame в CSV-строку
            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')

            st.download_button(
                label="📥 Скачать CSV файл",
                data=csv,
                file_name=f"drom_{model_path.replace('/', '_')}.csv",
                mime="text/csv",
            )
        else:
            st.warning("Не удалось собрать данные. Проверьте правильность модели или попробуйте позже.")