import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import pandas as pd
import io

TOKEN = '8049694744:AAFT2emdq3IL_uWFisDaN2va9m404l3UDaQ'

sales_data = None

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        'Привет! Я твой бот для Ozon-отчётов 💼\n\n'
        'Пришли по очереди два Excel-файла:\n'
        '1. Отчёт по продажам (где есть "Заказано товаров", "Отменено товаров", "Возвращено товаров")\n'
        '2. Отчёт по рекламе (Аналитика продвижения, где есть "Расход, ₽")\n\n'
        'Результаты пришлю в виде Excel-файлов!'
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global sales_data
    document = await update.message.document.get_file()
    file_bytes = await document.download_as_bytearray()
    file_io = io.BytesIO(file_bytes)

    try:
        df = pd.read_excel(file_io)

        # 1. Отчёт по продажам
        if 'Заказано товаров' in df.columns or 'Заказы' in df.columns:
            if 'Заказано товаров' in df.columns:
                df['Чистые_заказы'] = df['Заказано товаров']
            else:
                df['Чистые_заказы'] = df['Заказы']

            for col in ['Отменено товаров', 'Возвращено товаров', 'Отмены', 'Возвраты']:
                if col in df.columns:
                    df['Чистые_заказы'] -= df[col]

            sales_data = df[['Ozon ID', 'Чистые_заказы']].copy()
            sales_data = sales_data[sales_data['Чистые_заказы'] > 0]

            # Отправляем как Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                sales_data.to_excel(writer, index=False, sheet_name='Чистые заказы')
            output.seek(0)

            await update.message.reply_document(
                document=output,
                filename='чистые_заказы.xlsx',
                caption='Продажи обработаны! Чистые заказы (только >0) в файле.\nПришли теперь отчёт по рекламе.'
            )

        # 2. Отчёт по рекламе — гибкое распознавание
        elif any('расход' in col.lower() for col in df.columns):
            if sales_data is None:
                await update.message.reply_text('Сначала пришли отчёт по продажам!')
                return

            # Находим столбец с расходами
            adv_col = next(col for col in df.columns if 'расход' in col.lower())
            df_adv = df[['SKU', adv_col]].copy()

            merged = pd.merge(df_adv, sales_data, left_on='SKU', right_on='Ozon ID', how='left')
            merged['Затраты_на_1_заказ'] = (merged[adv_col] / merged['Чистые_заказы'].replace(0, float('nan'))).round(2)
            merged = merged.dropna(subset=['Затраты_на_1_заказ'])

            # Отправляем как Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                merged[['SKU', adv_col, 'Затраты_на_1_заказ']].to_excel(writer, index=False, sheet_name='Затраты')
            output.seek(0)

            await update.message.reply_document(
                document=output,
                filename='затраты_на_1_заказ.xlsx',
                caption='Реклама обработана! Затраты на 1 чистый заказ в файле.'
            )

        else:
            await update.message.reply_text(
                'Не распознал файл. Для продаж — нужен столбец "Заказано товаров".\n'
                'Для рекламы — нужен столбец с "Расход" (например "Расход, ₽").'
            )

    except Exception as e:
        await update.message.reply_text(f'Ошибка: {str(e)}\nПришли файл заново или скрин столбцов.')

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
