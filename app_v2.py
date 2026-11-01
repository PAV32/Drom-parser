"""
DROM MASTER ANALYTICS (ФИНАЛЬНАЯ ВЕРСИЯ С КЛИКАБЕЛЬНЫМИ ССЫЛКАМИ)
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import time
import random
import re
import sqlite3
from datetime import datetime
from typing import List, Dict, Any
import plotly.express as px
from sklearn.ensemble import RandomForestRegressor

# ==========================================
# 1. КОНСТАНТЫ И НАСТРОЙКИ
# ==========================================
DB_NAME = 'drom_master.db'
BASE_URL = "https://auto.drom.ru/region25/"

BRAND_MODELS: Dict[str, List[str]] = {
    "Nissan": ["Все модели", "Note", "X-Trail", "Leaf", "Serena", "Tiida"],
    "Toyota": ["Все модели", "Prius", "Camry", "Corolla", "Harrier"],
    "Honda": ["Все модели", "Fit", "Vezel", "CR-V", "Stepwgn"],
    "Subaru": ["Все модели", "Forester", "Impreza", "Legacy"],
    "Mazda": ["Все модели", "Demio", "CX-5", "CX-3"],
}

# ==========================================
# 2. БАЗА ДАННЫХ (SQLite)
# ==========================================
def init_db() -> None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cars (
            link TEXT PRIMARY KEY,
            brand TEXT,
            real_model TEXT,
            title TEXT,
            year INTEGER,
            engine REAL,
            price INTEGER,
            condition TEXT,
            location TEXT,
            first_seen TEXT,
            last_seen TEXT,
            initial_price INTEGER,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(df_today: pd.DataFrame) -> None:
    if df_today.empty:
        return
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT link, price, status FROM cars")
    existing_cars = {row[0]: {"price": row[1], "status": row[2]} for row in cursor.fetchall()}
    today_links = set(df_today['Link'].tolist())

    for _, row in df_today.iterrows():
        link = row['Link']
        if link in existing_cars:
            old_price = existing_cars[link]["price"]
            if row['Price'] < old_price:
                cursor.execute("UPDATE cars SET price=?, last_seen=?, status='Цена упала!' WHERE link=?", (row['Price'], today_date, link))
            else:
                cursor.execute("UPDATE cars SET last_seen=?, status='В продаже' WHERE link=?", (today_date, link))
        else:
            cursor.execute('''
                INSERT INTO cars (link, brand, real_model, title, year, engine, price, condition, location, first_seen, last_seen, initial_price, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'В продаже')
            ''', (link, row['Brand'], row['Real_Model'], row['Title'], row['Year'], row['Engine'], row['Price'], row['Condition'], row['Location'], today_date, today_date, row['Price']))

    for link, data in existing_cars.items():
        if link not in today_links and data["status"] != "Продана/Снята":
            cursor.execute("UPDATE cars SET status='Продана/Снята' WHERE link=?", (link,))

    conn.commit()
    conn.close()

# ==========================================
# 3. ПАРСЕР
# ==========================================
def parse_drom(brand: str, model: str, max_pages: int, status_box: Any, progress_bar: Any) -> pd.DataFrame:
    all_data: List[Dict[str, Any]] = []
    session = requests.Session()
    session.trust_env = False
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

    brand_slug = brand.lower()
    if model != "Все модели":
        model_slug = model.lower().replace(' ', '-')
        path = f"{brand_slug}/{model_slug}/"
    else:
        path = f"{brand_slug}/all/"

    for page in range(1, max_pages + 1):
        status_box.text(f"Сбор {brand} {model}: страница {page} из {max_pages}...")
        url = f"{BASE_URL}{path}" if page == 1 else f"{BASE_URL}{path}page{page}/"

        try:
            response = session.get(url, timeout=15)
            if response.status_code != 200:
                break
            soup = BeautifulSoup(response.text, 'html.parser')
            cars = soup.find_all('div', attrs={"data-ftid": "bulls-list_bull"})
            if len(cars) == 0:
                break

            for car in cars:
                try:
                    price_tag = car.find('span', attrs={"data-ftid": "bull_price"})
                    price = int(price_tag.text.strip().replace('\xa0', '').replace(' ', '').replace('₽', '')) if price_tag else 0
                    desc_tag = car.find('div', attrs={"data-ftid": "bull_subtitle"})
                    desc = desc_tag.text.strip() if desc_tag else ''
                    broken_tag = car.find('div', attrs={"data-ftid": "bull_label_broken"})
                    condition = 'Требует ремонта' if broken_tag else 'Целый'
                    local_tag = car.find('span', attrs={"data-ftid": "bull_location"})
                    local = local_tag.text.strip() if local_tag else 'Неизвестно'
                    title_link_tag = car.find('a', attrs={'data-ftid': 'bull_title'})
                    link = title_link_tag.get('href') if title_link_tag else None
                    title = title_link_tag.find('h3').text.strip() if title_link_tag else "Без названия"

                    if not link: continue

                    year_match = re.search(r'\b(19|20)\d{2}\b', title)
                    year = int(year_match.group(0)) if year_match else 0
                    engine_match = re.search(r'(\d\.\d)', desc)
                    engine = float(engine_match.group(1)) if engine_match else 0.0
                    clean_model = title.split(',')[0].replace(brand, '').strip()

                    all_data.append({
                        'Brand': brand, 'Real_Model': clean_model,
                        'Title': title, 'Year': year, 'Engine': engine,
                        'Price': price, 'Condition': condition,
                        'Location': local, 'Link': link
                    })
                except Exception:
                    pass
        except Exception:
            time.sleep(10)
            continue
        progress_bar.progress(page / max_pages)
        time.sleep(random.uniform(1.5, 3.0))
    return pd.DataFrame(all_data)

# ==========================================
# 4. ИНТЕРФЕЙС (STREAMLIT)
# ==========================================
st.set_page_config(page_title="Drom Master Analytics", page_icon="🚗", layout="wide")
st.title("🚗 Drom Master Analytics")
st.markdown("Промышленная система сбора, трекинга и ML-анализа авторынка Приморья.")

init_db()
if 'current_df' not in st.session_state:
    st.session_state.current_df = None

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⚙️ Парсинг", "📋 Текущие данные", "📈 Базовая аналитика", "🔬 Продвинутая аналитика (ML)", "🔥 Уставшие продавцы (БД)"
])

# --- ВКЛАДКА 1: ПАРСИНГ ---
with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        selected_brand = st.selectbox("Марка", list(BRAND_MODELS.keys()))
        selected_model = st.selectbox("Модель", BRAND_MODELS[selected_brand])
        max_pages = st.slider("Макс. страниц (1 стр ≈ 20 машин)", 1, 80, 5)
        start_btn = st.button("🚀 Запустить парсинг", type="primary")
    with col2:
        status_box = st.empty()
        progress_bar = st.progress(0)

    if start_btn:
        df = parse_drom(selected_brand, selected_model, max_pages, status_box, progress_bar)
        if not df.empty:
            st.session_state.current_df = df
            save_to_db(df)
            status_box.success(f"✅ Успех! Собрано {len(df)} машин. База обновлена.")
        else:
            status_box.error("❌ Данные не собраны.")

# --- ВКЛАДКА 2: ТЕКУЩИЕ ДАННЫЕ ---
with tab2:
    if st.session_state.current_df is not None and not st.session_state.current_df.empty:
        df = st.session_state.current_df
        st.subheader("Сырые данные (текущая выгрузка)")

        # ДОБАВЛЕНА КЛИКАБЕЛЬНАЯ ССЫЛКА
        st.dataframe(
            df,
            column_config={
                "Link": st.column_config.LinkColumn("Ссылка на объявление", display_text="Открыть"),
                "Price": st.column_config.NumberColumn("Цена", format="%d ₽")
            },
            use_container_width=True,
            hide_index=True
        )

        csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 Скачать CSV", data=csv, file_name="drom_current.csv", mime="text/csv")
    else:
        st.info("Сначала выполните парсинг на первой вкладке.")

# --- ВКЛАДКА 3: БАЗОВАЯ АНАЛИТИКА ---
with tab3:
    if st.session_state.current_df is not None and not st.session_state.current_df.empty:
        df = st.session_state.current_df
        df_valid = df[df['Price'] > 0].copy()

        if not df_valid.empty:
            st.subheader("Обзор рынка")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Объявлений", len(df_valid))
            m2.metric("Медиана", f"{int(df_valid['Price'].median()):,} ₽".replace(',', ' '))
            avg_age = 2026 - int(df_valid[df_valid['Year'] > 0]['Year'].mean()) if not df_valid[df_valid['Year'] > 0].empty else 0
            m3.metric("Средний возраст", f"{avg_age} лет")
            m4.metric("Доля битых", f"{(len(df_valid[df_valid['Condition'] == 'Требует ремонта']) / len(df_valid) * 100):.1f}%")

            df_year_valid = df_valid[df_valid['Year'] > 0]
            if not df_year_valid.empty:
                fig = px.scatter(df_year_valid, x='Year', y='Price', color='Condition',
                                 trendline="ols", color_discrete_map={'Целый': '#17b978', 'Требует ремонта': '#ff4b4b'})
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.subheader("🔥 Вкусные цены (Медиана по Модели+Году)")

            df_valid['Median_Model_Year'] = df_valid.groupby(['Real_Model', 'Year'])['Price'].transform('median')
            df_valid['Diff_%'] = np.where(
                df_valid['Median_Model_Year'] > 0,
                ((df_valid['Price'] - df_valid['Median_Model_Year']) / df_valid['Median_Model_Year']) * 100,
                0
            )

            bargains = df_valid[df_valid['Diff_%'] <= -15].sort_values('Diff_%')
            if not bargains.empty:
                # ДОБАВЛЕНА КЛИКАБЕЛЬНАЯ ССЫЛКА
                st.dataframe(
                    bargains[['Real_Model', 'Title', 'Year', 'Price', 'Median_Model_Year', 'Diff_%', 'Link']],
                    column_config={
                        "Link": st.column_config.LinkColumn("Ссылка", display_text="Открыть"),
                        "Price": st.column_config.NumberColumn("Цена", format="%d ₽"),
                        "Median_Model_Year": st.column_config.NumberColumn("Медиана", format="%d ₽"),
                        "Diff_%": st.column_config.NumberColumn("Отклонение", format="%.1f%%")
                    },
                    use_container_width=True
                )
            else:
                st.info("Выгодных предложений по медиане не найдено.")
    else:
        st.info("Сначала выполните парсинг.")

# --- ВКЛАДКА 4: ПРОДВИНУТАЯ АНАЛИТИКА (ML) ---
with tab4:
    if st.session_state.current_df is not None and not st.session_state.current_df.empty:
        df = st.session_state.current_df
        df_valid = df[(df['Price'] > 0) & (df['Year'] > 0)].copy()

        if len(df_valid) < 15:
            st.warning("Для ML нужно хотя бы 15 машин с ценами и годами. Расширьте выборку.")
        else:
            st.header("🔬 Data Science (Поиск аномалий)")

            # 1. Z-SCORE
            st.subheader("1. Z-Score (Стандартное отклонение)")
            grouped = df_valid.groupby(['Real_Model', 'Year'])['Price']
            mean_price = grouped.transform('mean')
            std_price = grouped.transform('std')
            df_valid['Z_Score'] = (df_valid['Price'] - mean_price) / std_price
            df_valid['Z_Score'] = df_valid['Z_Score'].fillna(0)

            z_bargains = df_valid[df_valid['Z_Score'] < -1.5].sort_values('Z_Score')
            if not z_bargains.empty:
                st.write(f"Найдено **{len(z_bargains)}** машин с аномально низкой ценой (Z < -1.5):")
                # ДОБАВЛЕНА КЛИКАБЕЛЬНАЯ ССЫЛКА
                st.dataframe(
                    z_bargains[['Title', 'Year', 'Price', 'Z_Score', 'Link']],
                    column_config={
                        "Link": st.column_config.LinkColumn("Ссылка", display_text="Открыть"),
                        "Price": st.column_config.NumberColumn("Цена", format="%d ₽")
                    },
                    use_container_width=True
                )
            else:
                st.info("Аномалий по Z-score нет.")

            st.markdown("---")

            # 2. IQR
            st.subheader("2. IQR (Межквартильный размах)")
            def get_iqr_lower_bound(x):
                Q1 = x.quantile(0.25)
                Q3 = x.quantile(0.75)
                IQR = Q3 - Q1
                return Q1 - 1.5 * IQR

            df_valid['IQR_Lower_Bound'] = df_valid.groupby(['Real_Model', 'Year'])['Price'].transform(get_iqr_lower_bound)
            iqr_bargains = df_valid[df_valid['Price'] < df_valid['IQR_Lower_Bound']].sort_values('Price')

            if not iqr_bargains.empty:
                st.write(f"Найдено **{len(iqr_bargains)}** выбросов ниже границы IQR:")
                # ДОБАВЛЕНА КЛИКАБЕЛЬНАЯ ССЫЛКА
                st.dataframe(
                    iqr_bargains[['Title', 'Year', 'Price', 'IQR_Lower_Bound', 'Link']],
                    column_config={
                        "Link": st.column_config.LinkColumn("Ссылка", display_text="Открыть"),
                        "Price": st.column_config.NumberColumn("Цена", format="%d ₽"),
                        "IQR_Lower_Bound": st.column_config.NumberColumn("Граница IQR", format="%d ₽")
                    },
                    use_container_width=True
                )
            else:
                st.info("Выбросов по IQR нет.")

            st.markdown("---")

            # 3. MACHINE LEARNING
            st.subheader("3. Машинное обучение (Random Forest)")
            ml_df = df_valid.copy()
            ml_df = ml_df[ml_df['Engine'] > 0]

            if len(ml_df) < 15:
                st.warning("Слишком мало машин с известным объемом двигателя для ML.")
            else:
                ml_df['Is_Broken'] = ml_df['Condition'].apply(lambda x: 1 if x == 'Требует ремонта' else 0)
                X = ml_df[['Year', 'Engine', 'Is_Broken']]
                y = ml_df['Price']

                model = RandomForestRegressor(n_estimators=100, random_state=42)
                model.fit(X, y)

                ml_df['Predicted_Price'] = model.predict(X)
                ml_df['Residual_%'] = ((ml_df['Price'] - ml_df['Predicted_Price']) / ml_df['Predicted_Price']) * 100
                ml_bargains = ml_df[ml_df['Residual_%'] < -20].sort_values('Residual_%')

                fig_ml = px.scatter(ml_df, x='Predicted_Price', y='Price', color='Residual_%',
                                    color_continuous_scale='RdYlGn', hover_data=['Title'])
                max_val = max(ml_df['Price'].max(), ml_df['Predicted_Price'].max())
                fig_ml.add_shape(type="line", x0=0, y0=0, x1=max_val, y1=max_val, line=dict(color="black", dash="dash"))
                st.plotly_chart(fig_ml, use_container_width=True)

                if not ml_bargains.empty:
                    st.write(f"🔥 ML-модель нашла **{len(ml_bargains)}** недооцененных машин (ниже прогноза на 20%+):")
                    # ДОБАВЛЕНА КЛИКАБЕЛЬНАЯ ССЫЛКА
                    st.dataframe(
                        ml_bargains[['Title', 'Year', 'Price', 'Predicted_Price', 'Residual_%', 'Link']],
                        column_config={
                            "Link": st.column_config.LinkColumn("Ссылка", display_text="Открыть"),
                            "Price": st.column_config.NumberColumn("Реальная цена", format="%d ₽"),
                            "Predicted_Price": st.column_config.NumberColumn("Прогноз ML", format="%d ₽"),
                            "Residual_%": st.column_config.NumberColumn("Недооценка", format="%.1f%%"),
                        },
                        use_container_width=True
                    )
                else:
                    st.info("ML не нашел явных недооценок (ниже прогноза на 20%).")
    else:
        st.info("Сначала выполните парсинг.")

# --- ВКЛАДКА 5: УСТАВШИЕ ПРОДАВЦЫ ---
with tab5:
    st.subheader("🔥 Анализ истории (База данных)")
    conn = sqlite3.connect(DB_NAME)

    query_drops = """
        SELECT title, year, location, initial_price, price, 
               (initial_price - price) as drop_amount,
               ROUND(((initial_price - price) * 100.0 / initial_price), 1) as drop_percent,
               link
        FROM cars 
        WHERE price < initial_price AND status != 'Продана/Снята'
        ORDER BY drop_percent DESC
    """
    df_drops = pd.read_sql_query(query_drops, conn)

    query_long = """
        SELECT title, year, price, first_seen, last_seen, link
        FROM cars 
        WHERE status IN ('В продаже', 'Цена упала!')
        ORDER BY first_seen ASC
    """
    df_long = pd.read_sql_query(query_long, conn)
    conn.close()

    if not df_drops.empty:
        st.write(f"📉 **Найдено {len(df_drops)} машин, на которые упала цена:**")
        st.dataframe(
            df_drops,
            column_config={
                "Link": st.column_config.LinkColumn("Ссылка", display_text="Открыть"),
                "initial_price": st.column_config.NumberColumn("Было", format="%d ₽"),
                "price": st.column_config.NumberColumn("Стало", format="%d ₽"),
                "drop_amount": st.column_config.NumberColumn("Скинул", format="%d ₽"),
                "drop_percent": st.column_config.NumberColumn("% скидки", format="%.1f%%")
            },
            use_container_width=True, hide_index=True
        )
    else:
        st.info("Пока нет машин с упавшей ценой. Запустите парсер завтра, чтобы увидеть динамику.")

    st.markdown("---")

    if not df_long.empty:
        st.write(f"🕒 **Машины в базе (висят дольше всего):**")
        st.dataframe(
            df_long,
            column_config={
                "Link": st.column_config.LinkColumn("Ссылка", display_text="Открыть"),
                "Price": st.column_config.NumberColumn("Цена", format="%d ₽"),
                "first_seen": "Дата появления",
                "last_seen": "Последний раз в продаже"
            },
            use_container_width=True, hide_index=True
        )