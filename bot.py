import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import pandas as pd
import io

# Твой реальный токен уже здесь ↓
TOKEN = '8049694744:AAFT2emdq3IL_uWFisDaN2va9m404l3UDaQ'

# Временное хранилище данных продаж (для расчёта рекламы)
sales_data = None

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        'Привет! Я твой бот для Ozon-отчётов 💼\n\n'
        'Пришли мне по очереди два Excel-файла:\n'
        '1. Сначала — отчёт по продажам за вчера (аналитика продаж)\n'
        '2. Потом — отчёт по рекламе\n\n'
        'Я посчитаю:\n'
        '• Чистые заказы = Заказы − Возвраты − Отмены\n'
        '• Затраты на 1 чистый заказ = Сумма рекламы / Чистые заказы\n\n'
        'Жду первый файл! 📊'
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global sales_data
    document = await update.message.document.get_file()
    file_bytes = await document.download_as_bytearray()
    file_io = io.BytesIO(file_bytes)

    try:
        df = pd.read_excel(file_io)

        # Если это отчёт по продажам
        if 'Заказы' in df.columns or 'Заказано товаров' in df.columns:
            # Адаптировано под твои реальные столбцы
            if 'Заказано товаров' in df.columns:
                df['Чистые_заказы'] = df['Заказано товаров']
            else:
                df['Чистые_заказы'] = df['Заказы']

            if 'Отменено товаров' in df.columns:
                df['Чистые_заказы'] -= df['Отменено товаров']
            if 'Возвращено товаров' in df.columns:
                df['Чистые_заказы'] -= df['Возвращено товаров']

            # Используем Ozon ID как ключевой столбец
            sales_data = df[['Ozon ID', 'Чистые_заказы']].copy()
            sales_data = sales_data[sales_data['Чистые_заказы'] > 0]  # только положительные
            result_text = sales_data.to_string(index=False)
            await update.message.reply_text(
                f'Отчёт по продажам обработан!\nЧистые заказы по Ozon ID:\n\n{result_text}\n\n'
                'Теперь пришли отчёт по рекламе 📈'
            )

        # Если это отчёт по рекламе
        elif 'Расход, ₽' in df.columns:
            if sales_data is None:
                await update.message.reply_text('Сначала пришли отчёт по продажам!')
                return

            df_adv = df[['SKU', 'Расход, ₽']].copy()
            merged = pd.merge(df_adv, sales_data, left_on='SKU', right_on='Ozon ID', how='left')
            merged['Затраты_на_1_заказ'] = (merged['Расход, ₽'] / merged['Чистые_заказы'].replace(0, float('nan'))).round(2)
            merged = merged.dropna(subset=['Затраты_на_1_заказ'])  # убираем NaN
            result_text = merged[['SKU', 'Затраты_на_1_заказ']].to_string(index=False)
            await update.message.reply_text(
                f'Отчёт по рекламе обработан!\nЗатраты на 1 чистый заказ:\n\n{result_text}\n\n'
                'Готово! Можешь присылать новые отчёты.'
            )

        else:
            await update.message.reply_text('Не узнал формат файла. Пришли Excel-отчёт от Ozon (продажи или реклама).')

    except Exception as e:
        await update.message.reply_text(f'Ошибка обработки:\n{str(e)}\nПопробуй прислать файл заново.')

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
