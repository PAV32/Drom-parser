import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import random
import re
import plotly.express as px
import io

# ==========================================
# 1. НАСТРОЙКА И ДИЗАЙН (UI/UX)
# ==========================================
st.set_page_config(page_title="Drom Pro Analytics", page_icon="🚘", layout="wide", initial_sidebar_state="expanded")

# Кастомный CSS: скрываем дефолтное меню, делаем красивый фон и шрифты
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 2rem;}
    h1 { color: #0E1117; font-weight: 800; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)


# ==========================================
# 2. ФУНКЦИИ ПАРСИНГА (С КЭШИРОВАНИЕМ)
# ==========================================
# @st.cache_data - это магия. Если вызвать функцию с теми же аргументами,
# Streamlit возьмет данные из памяти, а не будет заново долбить сайт.
@st.cache_data(ttl=3600, show_spinner=False)
def scrape_drom(models_list, max_pages):
    all_data = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    progress_bar = st.progress(0)
    status_text = st.empty()

    total_tasks = len(models_list) * max_pages
    task_count = 0

    for model_path in models_list:
        for page in range(1, max_pages + 1):
            task_count += 1
            status_text.text(f"Сканируем: {model_path} | Страница {page}/{max_pages}")

            url = f"https://auto.drom.ru/region25/{model_path}/all/" if page == 1 else f"https://auto.drom.ru/region25/{model_path}/all/page{page}/"

            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    cars = soup.find_all('div', attrs={"data-ftid": "bulls-list_bull"})

                    for car in cars:
                        try:
                            price_tag = car.find('span', attrs={"data-ftid": "bull_price"})
                            price = int(price_tag.text.strip().replace('\xa0', '').replace(' ', '').replace('₽',
                                                                                                            '')) if price_tag else 0

                            desc_tag = car.find('div', attrs={"data-ftid": "bull_subtitle"})
                            description = desc_tag.text.strip() if desc_tag else ''

                            broken_tag = car.find('div', attrs={"data-ftid": "bull_label_broken"})
                            condition = 'Битый' if broken_tag else 'Целый'

                            local_tag = car.find('span', attrs={"data-ftid": "bull_location"})
                            local = local_tag.text.strip() if local_tag else 'Неизвестно'

                            title_link_tag = car.find('a', attrs={'data-ftid': 'bull_title'})
                            link = title_link_tag.get('href') if title_link_tag else ""
                            title = title_link_tag.find('h3').text.strip() if title_link_tag else ""

                            # --- АВТОМАТИЧЕСКАЯ ОЧИСТКА (Regex) ---
                            # Ищем 4 цифры, начинающиеся с 19 или 20 (год выпуска)
                            year_match = re.search(r'\b(19|20)\d{2}\b', title)
                            year = int(year_match.group(0)) if year_match else 0

                            # Ищем объем двигателя (например, 1.5, 2.0)
                            engine_match = re.search(r'(\d\.\d)', description)
                            engine = float(engine_match.group(1)) if engine_match else 0.0

                            # Ищем мощность (л.с.)
                            hp_match = re.search(r'(\d+)\s*(л\.с\.|hp)', description)
                            hp = int(hp_match.group(1)) if hp_match else 0

                            all_data.append({
                                'Model': model_path.upper(),
                                'Title': title,
                                'Year': year,
                                'Price': price,
                                'Engine_Vol': engine,
                                'Horsepower': hp,
                                'Condition': condition,
                                'Location': local,
                                'Link': link
                            })
                        except Exception:
                            pass
            except Exception:
                pass

            progress_bar.progress(task_count / total_tasks)
            time.sleep(random.uniform(1.5, 3.0))

    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(all_data)


# ==========================================
# 3. ИНТЕРФЕЙС
# ==========================================
st.title("🚘 Drom Pro Analytics")
st.markdown("Профессиональный анализ рынка авто Приморья.")

# Боковая панель (Sidebar) для настроек
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Drom.ru_logo.svg/1200px-Drom.ru_logo.svg.png",
             width=150)
    st.header("Параметры сбора")

    models_input = st.text_area("Модели (каждая с новой строки)", "nissan/note\nhonda/fit\ntoyota/prius")
    max_pages = st.slider("Страниц на модель", 1, 20, 3)

    start_btn = st.button("🚀 Запустить анализ", use_container_width=True)

    st.markdown("---")
    st.caption("Разработано на Python + Streamlit")

# Логика работы
if start_btn:
    models = [m.strip() for m in models_input.split('\n') if m.strip()]
    with st.spinner("Собираем данные с Дрома... Это может занять пару минут."):
        df = scrape_drom(models, max_pages)
        st.session_state['df'] = df
        st.session_state['last_update'] = time.strftime("%Y-%m-%d %H:%M")

# Если данные есть, показываем дашборд
if 'df' in st.session_state and not st.session_state['df'].empty:
    df = st.session_state['df'].copy()

    # --- БЛОК ФИЛЬТРОВ ---
    with st.expander("⚙️ Фильтры данных", expanded=True):
        col1, col2, col3, col4 = st.columns(4)

        # Фильтр по цене (игнорируем нули)
        valid_prices = df[df['Price'] > 0]['Price']
        min_p, max_p = int(valid_prices.min()), int(valid_prices.max())
        price_range = col1.slider("Цена (₽)", min_p, max_p, (min_p, max_p), step=50000)

        # Фильтр по годам
        valid_years = df[df['Year'] > 0]['Year']
        min_y, max_y = int(valid_years.min()), int(valid_years.max())
        year_range = col2.slider("Год выпуска", min_y, max_y, (min_y, max_y))

        # Фильтр по состоянию
        condition = col3.multiselect("Состояние", ['Целый', 'Битый'], default=['Целый', 'Битый'])

        # Фильтр по локации
        locations = col4.multiselect("Локация", df['Location'].unique(), default=df['Location'].unique())

    # Применяем фильтры
    filtered_df = df[
        (df['Price'] >= price_range[0]) & (df['Price'] <= price_range[1]) &
        (df['Year'] >= year_range[0]) & (df['Year'] <= year_range[1]) &
        (df['Condition'].isin(condition)) &
        (df['Location'].isin(locations))
        ]

    # --- ВКЛАДКИ ДАШБОРДА ---
    tab1, tab2, tab3 = st.tabs(["📈 Дашборд (Обзор)", "🔍 Таблица данных", "📥 Экспорт"])

    # Вкладка 1: Аналитика
    with tab1:
        # Метрики
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Найдено машин", len(filtered_df))
        c2.metric("Медианная цена", f"{int(filtered_df['Price'].median()):,} ₽".replace(',', ' '))
        c3.metric("Средний год", int(filtered_df['Year'].mean()))

        # Самый популярный город
        top_loc = filtered_df['Location'].mode()[0] if not filtered_df.empty else "Нет"
        c4.metric("Топ локация", top_loc)

        st.markdown("---")

        # Графики
        g1, g2 = st.columns(2)

        with g1:
            st.subheader("Цена vs Год выпуска")
            # Точечный график: каждый кружок - машина.
            fig_scatter = px.scatter(
                filtered_df, x='Year', y='Price', color='Condition',
                hover_data=['Title', 'Location'], size='Horsepower',
                color_discrete_map={'Целый': '#17b978', 'Битый': '#ff4b4b'}
            )
            fig_scatter.update_layout(height=400)
            st.plotly_chart(fig_scatter, use_container_width=True)

        with g2:
            st.subheader("Распределение цен по локациям (Boxplot)")
            # Boxplot показывает медиану и выбросы (очень круто для авто)
            fig_box = px.box(filtered_df, x='Location', y='Price', color='Location')
            fig_box.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig_box, use_container_width=True)

    # Вкладка 2: Таблица
    with tab2:
        st.dataframe(
            filtered_df,
            column_config={
                "Link": st.column_config.LinkColumn("Ссылка", display_text="Открыть"),
                "Price": st.column_config.NumberColumn("Цена", format="%d ₽"),
                "Horsepower": st.column_config.NumberColumn("Л.С.", format="%d")
            },
            use_container_width=True,
            hide_index=True
        )

    # Вкладка 3: Экспорт
    with tab3:
        st.subheader("Скачать данные")
        st.write("Выгрузите данные в удобном формате.")

        # 1. CSV
        csv = filtered_df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📄 Скачать CSV", data=csv, file_name="drom_data.csv", mime="text/csv")

        # 2. Excel (Два листа)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # Лист 1: Все данные
            filtered_df.to_excel(writer, sheet_name='Данные', index=False)

            # Лист 2: Аналитика (Сводная таблица по городам)
            pivot = filtered_df.pivot_table(index='Location', values='Price',
                                            aggfunc=['count', 'median', 'mean']).round(0)
            pivot.to_excel(writer, sheet_name='Аналитика')

        st.download_button(
            label="📊 Скачать Excel (Данные + Аналитика)",
            data=buffer.getvalue(),
            file_name="drom_analytics.xlsx",
            mime="application/vnd.ms-excel"
        )
else:
    st.info("👈 Настройте параметры в левом меню и нажмите «Запустить анализ», чтобы построить дашборд.")