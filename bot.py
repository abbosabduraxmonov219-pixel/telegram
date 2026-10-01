import sqlite3
import logging
from pathlib import Path
from datetime import datetime

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)


# ============================================================
# SOZLAMALAR
# ============================================================

TOKEN = "8808158727:AAGVgr-e2rJc7oSHAht3EqqYGU0JorpVKc4"

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "baza.db"


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def quote_identifier(name):
    return '"' + str(name).replace('"', '""') + '"'


def table_columns(table_name):
    conn = db()

    rows = conn.execute(
        f"PRAGMA table_info({quote_identifier(table_name)})"
    ).fetchall()

    conn.close()

    return [row["name"] for row in rows]


def find_column(columns, candidates):
    """
    Ustun nomini avtomatik topadi.
    Masalan:
    ID
    id
    Employee ID
    Xodim ID
    """
    normalized = {}

    for col in columns:
        key = (
            str(col)
            .strip()
            .lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("-", "")
        )

        normalized[key] = col

    # 1. Aniq nom
    for candidate in candidates:
        key = (
            str(candidate)
            .strip()
            .lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("-", "")
        )

        if key in normalized:
            return normalized[key]

    # 2. Ichida mavjudligini tekshirish
    for col in columns:
        c = (
            str(col)
            .strip()
            .lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("-", "")
        )

        for candidate in candidates:
            x = (
                str(candidate)
                .strip()
                .lower()
                .replace(" ", "")
                .replace("_", "")
                .replace("-", "")
            )

            if x in c or c in x:
                return col

    return None


# ============================================================
# JADVAL TUZILMASINI ANIQLASH
# ============================================================

def get_employee_structure():
    columns = table_columns("employees")

    # ID
    id_col = find_column(
        columns,
        [
            "employee_id",
            "employeeid",
            "id",
            "ID",
            "xodim_id",
            "xodimid",
            "xodim kodi",
            "xodimkodi",
        ],
    )

    # Ism
    name_col = find_column(
        columns,
        [
            "name",
            "ism",
            "ismi",
            "fio",
            "FIO",
            "xodim",
            "xodim ismi",
            "fullname",
            "full_name",
        ],
    )

    # Lavozim
    position_col = find_column(
        columns,
        [
            "position",
            "lavozim",
            "ishi",
            "ish",
            "role",
            "rol",
            "должность",
        ],
    )

    # Dastavka
    delivery_col = find_column(
        columns,
        [
            "delivery_code",
            "deliverycode",
            "dastavka",
            "dastavka kodi",
            "dastavkakodi",
            "dostavka",
            "dostavka kodi",
            "subscriberext",
        ],
    )

    # Agar nomlar topilmasa, Excel A-D tartibidan foydalanamiz
    if len(columns) >= 4:

        if id_col is None:
            id_col = columns[1]

        if name_col is None:
            name_col = columns[0]

        if position_col is None:
            position_col = columns[2]

        if delivery_col is None:
            delivery_col = columns[3]

    return {
        "columns": columns,
        "id": id_col,
        "name": name_col,
        "position": position_col,
        "delivery": delivery_col,
    }


def get_store_structure():
    columns = table_columns("stores")

    code_col = find_column(
        columns,
        [
            "store_code",
            "storecode",
            "clcode",
            "CLCODE",
            "code",
            "kod",
            "do'kon kodi",
            "dokon kodi",
        ],
    )

    name_col = find_column(
        columns,
        [
            "store_name",
            "storename",
            "title",
            "Title",
            "name",
            "nomi",
            "do'kon nomi",
            "dokon nomi",
        ],
    )

    region_col = find_column(
        columns,
        [
            "region",
            "Region",
            "city",
            "CITY",
            "viloyat",
            "shahar",
        ],
    )

    delivery_col = find_column(
        columns,
        [
            "delivery_code",
            "deliverycode",
            "subscriberext",
            "SUBSCRIBEREXT",
            "dastavka",
            "dastavka kodi",
            "dostavka",
        ],
    )

    # Sizdagi hozirgi baza:
    # A = CLCODE
    # B = Title
    # C = CITY
    # D = SUBSCRIBEREXT

    if len(columns) >= 4:

        if code_col is None:
            code_col = columns[0]

        if name_col is None:
            name_col = columns[1]

        if region_col is None:
            region_col = columns[2]

        if delivery_col is None:
            delivery_col = columns[3]

    return {
        "columns": columns,
        "code": code_col,
        "name": name_col,
        "region": region_col,
        "delivery": delivery_col,
    }


# ============================================================
# DATABASE TAYYORLASH
# ============================================================

def prepare_database():

    if not DB_FILE.exists():
        raise FileNotFoundError(
            f"baza.db topilmadi: {DB_FILE}"
        )

    conn = db()

    # Employees telegram_id
    employee_columns = table_columns("employees")

    if "telegram_id" not in employee_columns:
        conn.execute(
            """
            ALTER TABLE employees
            ADD COLUMN telegram_id INTEGER
            """
        )

    # Requests jadvali
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )
        """
    )

    request_columns = table_columns("requests")

    required_requests_columns = {
        "telegram_id": "INTEGER",
        "employee_id": "TEXT",
        "employee_name": "TEXT",
        "username": "TEXT",

        "store_code": "TEXT",
        "store_name": "TEXT",
        "region": "TEXT",

        "old_delivery": "TEXT",
        "new_delivery": "TEXT",

        "reason": "TEXT",

        "status": "TEXT",

        "manager_comment": "TEXT",
        "operator_comment": "TEXT",

        "manager_id": "TEXT",
        "manager_name": "TEXT",

        "created_at": "TEXT",
        "updated_at": "TEXT",
    }

    for column, data_type in required_requests_columns.items():

        if column not in request_columns:

            conn.execute(
                f"""
                ALTER TABLE requests
                ADD COLUMN {quote_identifier(column)}
                {data_type}
                """
            )

    conn.commit()
    conn.close()


# ============================================================
# NORMALIZATSIYA
# ============================================================

def normalize_code(value):

    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .replace(":", ".")
        .replace("-", ".")
        .replace(" ", "")
        .upper()
    )


def clean(value):

    if value is None:
        return ""

    return str(value).strip()


# ============================================================
# ROL ANIQLASH
# ============================================================

def parse_role(position):

    text = clean(position).lower()

    if "dastavka" in text:
        return "dastavka"

    if "dostavka" in text:
        return "dastavka"

    if "manager" in text:
        return "manager"

    if "menejer" in text:
        return "manager"

    if "operator" in text:
        return "operator"

    if "nazoratchi" in text:
        return "nazoratchi"

    if "nazorat" in text:
        return "nazoratchi"

    return "user"


# ============================================================
# XODIMNI TOPISH
# ============================================================

def get_employee_by_id(employee_id):

    structure = get_employee_structure()

    id_col = structure["id"]

    if not id_col:
        return None

    conn = db()

    row = conn.execute(
        f"""
        SELECT *
        FROM employees
        WHERE CAST({quote_identifier(id_col)} AS TEXT) = ?
        LIMIT 1
        """,
        (str(employee_id).strip(),),
    ).fetchone()

    conn.close()

    return row


def get_employee_by_telegram(telegram_id):

    structure = get_employee_structure()

    columns = structure["columns"]

    if "telegram_id" not in columns:
        return None

    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM employees
        WHERE telegram_id = ?
        LIMIT 1
        """,
        (telegram_id,),
    ).fetchone()

    conn.close()

    return row


def employee_data(row):

    structure = get_employee_structure()

    return {
        "id": clean(row[structure["id"]]),
        "name": clean(row[structure["name"]]),
        "position": clean(row[structure["position"]]),
        "delivery": clean(row[structure["delivery"]]),
    }


# ============================================================
# TELEGRAM ID BIRIKTIRISH
# ============================================================

def save_telegram_id(employee_id, telegram_id):

    structure = get_employee_structure()

    id_col = structure["id"]

    conn = db()

    # Avval shu Telegram ID boshqa xodimga tegishli bo'lsa,
    # olib tashlaymiz
    conn.execute(
        """
        UPDATE employees
        SET telegram_id = NULL
        WHERE telegram_id = ?
        """,
        (telegram_id,),
    )

    conn.execute(
        f"""
        UPDATE employees
        SET telegram_id = ?
        WHERE CAST({quote_identifier(id_col)} AS TEXT) = ?
        """,
        (
            telegram_id,
            str(employee_id).strip(),
        ),
    )

    conn.commit()
    conn.close()


# ============================================================
# DO'KON TOPISH
# ============================================================

def get_store(store_code):

    structure = get_store_structure()

    code_col = structure["code"]

    if not code_col:
        return None

    target = normalize_code(store_code)

    conn = db()

    # Avval aniq qidiruv
    rows = conn.execute(
        f"""
        SELECT *
        FROM stores
        """
    ).fetchall()

    conn.close()

    for row in rows:

        current = normalize_code(
            row[code_col]
        )

        if current == target:

            return {
                "code": clean(row[structure["code"]]),
                "name": clean(row[structure["name"]]),
                "region": clean(row[structure["region"]]),
                "delivery": clean(row[structure["delivery"]]),
            }

    return None


# ============================================================
# SO'ROV
# ============================================================

def get_request(request_id):

    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM requests
        WHERE id = ?
        """,
        (request_id,),
    ).fetchone()

    conn.close()

    return row


# ============================================================
# ID LAR
# ============================================================

def get_role_telegram_ids(role):

    structure = get_employee_structure()

    position_col = structure["position"]

    if not position_col:
        return []

    conn = db()

    rows = conn.execute(
        """
        SELECT telegram_id, *
        FROM employees
        WHERE telegram_id IS NOT NULL
        """
    ).fetchall()

    conn.close()

    result = []

    for row in rows:

        employee = employee_data(row)

        if parse_role(
            employee["position"]
        ) == role:

            if row["telegram_id"]:
                result.append(
                    row["telegram_id"]
                )

    return result


# ============================================================
# MENYULAR
# ============================================================

def dastavka_menu():

    return ReplyKeyboardMarkup(
        [
            ["🔎 Do'kon qidirish"],
            ["✏️ O'zgartirish kiritish"],
            ["📋 Mening so'rovlarim"],
            ["👤 Mening ma'lumotlarim"],
            ["🚪 Chiqish"],
        ],
        resize_keyboard=True,
    )


def manager_menu():

    return ReplyKeyboardMarkup(
        [
            ["📋 So'rovlar"],
            ["👤 Mening ma'lumotlarim"],
            ["🚪 Chiqish"],
        ],
        resize_keyboard=True,
    )


def operator_menu():

    return ReplyKeyboardMarkup(
        [
            ["📋 So'rovlar"],
            ["👤 Mening ma'lumotlarim"],
            ["🚪 Chiqish"],
        ],
        resize_keyboard=True,
    )


def nazoratchi_menu():

    return ReplyKeyboardMarkup(
        [
            ["🔎 Do'kon qidirish"],
            ["📋 So'rovlar"],
            ["📊 Hisobot"],
            ["🚚 Dastavkalar"],
            ["👤 Mening ma'lumotlarim"],
            ["🚪 Chiqish"],
        ],
        resize_keyboard=True,
    )


def get_menu(role):

    if role == "dastavka":
        return dastavka_menu()

    if role == "manager":
        return manager_menu()

    if role == "operator":
        return operator_menu()

    if role == "nazoratchi":
        return nazoratchi_menu()

    return ReplyKeyboardMarkup(
        [
            ["👤 Mening ma'lumotlarim"],
            ["🚪 Chiqish"],
        ],
        resize_keyboard=True,
    )


# ============================================================
# XODIM MA'LUMOTI
# ============================================================

def employee_info_text(employee):

    return (
        "👤 <b>Mening ma'lumotlarim</b>\n\n"
        f"👤 Ism: {employee['name']}\n"
        f"🆔 ID: {employee['id']}\n"
        f"💼 Lavozim: "
        f"{parse_role(employee['position']).upper()}\n"
        f"🚚 Dastavka kodi: "
        f"{employee['delivery'] or '-'}"
    )


# ============================================================
# DO'KON MATNI
# ============================================================

def store_text(store):

    return (
        "🏪 <b>Do'kon ma'lumotlari</b>\n\n"
        f"🔢 Kod: {store['code']}\n"
        f"🏷 Nomi: {store['name'] or '-'}\n"
        f"📍 Region: {store['region'] or '-'}\n"
        f"🚚 Biriktirilgan Dastavka: "
        f"{store['delivery'] or '-'}"
    )


# ============================================================
# START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    telegram_id = update.effective_user.id

    row = get_employee_by_telegram(
        telegram_id
    )

    if row:

        employee = employee_data(row)

        role = parse_role(
            employee["position"]
        )

        await update.message.reply_text(
            f"✅ Xush kelibsiz, "
            f"{employee['name']}!\n\n"
            f"👤 ID: {employee['id']}\n"
            f"💼 Lavozim: {role.upper()}\n"
            f"🚚 Dastavka kodi: "
            f"{employee['delivery'] or '-'}",
            reply_markup=get_menu(role),
        )

        return

    context.user_data[
        "awaiting_login"
    ] = True

    await update.message.reply_text(
        "Assalomu alaykum! 👋\n\n"
        "Botdan foydalanish uchun "
        "xodim ID raqamingizni yuboring."
    )


# ============================================================
# LOGIN
# ============================================================

async def login(update, context):

    employee_id = update.message.text.strip()

    row = get_employee_by_id(
        employee_id
    )

    if not row:

        await update.message.reply_text(
            "❌ Bunday xodim ID topilmadi.\n\n"
            "ID raqamingizni tekshirib "
            "qayta yuboring."
        )

        return

    employee = employee_data(row)

    save_telegram_id(
        employee["id"],
        update.effective_user.id,
    )

    context.user_data[
        "awaiting_login"
    ] = False

    role = parse_role(
        employee["position"]
    )

    await update.message.reply_text(
        f"✅ Xush kelibsiz, "
        f"{employee['name']}!\n\n"
        f"👤 ID: {employee['id']}\n"
        f"💼 Lavozim: {role.upper()}\n"
        f"🚚 Dastavka kodi: "
        f"{employee['delivery'] or '-'}",
        reply_markup=get_menu(role),
    )


# ============================================================
# DO'KON QIDIRISH
# ============================================================

async def store_search_start(update, context):

    context.user_data["mode"] = "store_search"

    await update.message.reply_text(
        "🔎 Do'kon kodini yuboring.\n\n"
        "Masalan:\n"
        "120.01.104.0653"
    )


async def store_search_handle(update, context):

    store = get_store(
        update.message.text
    )

    if not store:

        await update.message.reply_text(
            "❌ Bunday do'kon topilmadi.\n\n"
            "Do'kon kodini tekshirib "
            "qayta yuboring."
        )

        return

    await update.message.reply_text(
        store_text(store),
        parse_mode="HTML",
    )

    context.user_data["mode"] = None


# ============================================================
# O'ZGARTIRISH
# ============================================================

async def change_start(update, context):

    context.user_data[
        "mode"
    ] = "change_store"

    await update.message.reply_text(
        "✏️ <b>O'zgartirish kiritish</b>\n\n"
        "Do'kon kodini yuboring:",
        parse_mode="HTML",
    )


async def change_store_handle(update, context):

    store = get_store(
        update.message.text
    )

    if not store:

        await update.message.reply_text(
            "❌ Bunday do'kon topilmadi."
        )

        return

    context.user_data[
        "change_store"
    ] = store

    context.user_data[
        "mode"
    ] = "change_delivery"

    await update.message.reply_text(
        store_text(store)
        + "\n\n"
        "➡️ Yangi Dastavka kodini yuboring:",
        parse_mode="HTML",
    )


async def change_delivery_handle(update, context):

    new_delivery = update.message.text.strip()

    if not new_delivery:
        await update.message.reply_text(
            "❌ Dastavka kodini kiriting."
        )
        return

    context.user_data[
        "new_delivery"
    ] = new_delivery

    context.user_data[
        "mode"
    ] = "change_reason"

    await update.message.reply_text(
        "💬 O'zgartirish sababini yozing:"
    )


async def change_reason_handle(update, context):

    reason = update.message.text.strip()

    store = context.user_data.get(
        "change_store"
    )

    new_delivery = context.user_data.get(
        "new_delivery"
    )

    if not store or not new_delivery:

        await update.message.reply_text(
            "❌ So'rov ma'lumotlari topilmadi."
        )

        context.user_data.clear()

        return

    row = get_employee_by_telegram(
        update.effective_user.id
    )

    employee = employee_data(row)

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = db()

    cur = conn.execute(
        """
        INSERT INTO requests (
            telegram_id,
            employee_id,
            employee_name,
            username,
            store_code,
            store_name,
            region,
            old_delivery,
            new_delivery,
            reason,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            update.effective_user.id,
            employee["id"],
            employee["name"],
            update.effective_user.username or "",
            store["code"],
            store["name"],
            store["region"],
            store["delivery"],
            new_delivery,
            reason,
            "Yangi",
            now,
            now,
        ),
    )

    request_id = cur.lastrowid

    conn.commit()
    conn.close()

    context.user_data.clear()

    await update.message.reply_text(
        f"✅ So'rov yuborildi!\n\n"
        f"🆔 So'rov №{request_id}\n"
        f"🏪 Do'kon: {store['code']}\n"
        f"🚚 Hozirgi: {store['delivery'] or '-'}\n"
        f"➡️ Yangi: {new_delivery}\n"
        f"💬 Sabab: {reason}",
        reply_markup=dastavka_menu(),
    )

    await send_to_managers(
        context,
        request_id,
    )


# ============================================================
# SO'ROV MATNI
# ============================================================

def request_text(
    row,
    title="📋 YANGI DOSTAVKA SO‘ROVI",
):

    return (
        f"<b>{title}</b>\n\n"
        f"🆔 So'rov №{row['id']}\n"
        f"👤 Xodim: "
        f"{row['employee_name'] or '-'}\n"
        f"🏪 Do'kon kodi: "
        f"{row['store_code'] or '-'}\n"
        f"🏬 Do'kon: "
        f"{row['store_name'] or '-'}\n"
        f"📍 Region: "
        f"{row['region'] or '-'}\n"
        f"🚚 Hozirgi yo'nalish: "
        f"{row['old_delivery'] or '-'}\n"
        f"➡️ Yangi yo'nalish: "
        f"{row['new_delivery'] or '-'}\n"
        f"💬 Izoh: "
        f"{row['reason'] or '-'}\n\n"
        "━━━━━━━━━━━━━━"
    )


# ============================================================
# MANAGERGA YUBORISH
# ============================================================

async def send_to_managers(
    context,
    request_id,
):

    row = get_request(
        request_id
    )

    if not row:
        return

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ TASDIQLASH",
                    callback_data=
                    f"manager_approve:{request_id}",
                ),
                InlineKeyboardButton(
                    "❌ BEKOR QILISH",
                    callback_data=
                    f"manager_cancel:{request_id}",
                ),
            ]
        ]
    )

    for telegram_id in get_role_telegram_ids(
        "manager"
    ):

        try:

            await context.bot.send_message(
                chat_id=telegram_id,
                text=request_text(row),
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        except Exception as e:

            logger.error(
                f"Managerga xato: {e}"
            )


# ============================================================
# MANAGER SO'ROVLARI
# ============================================================

async def manager_requests(
    update,
    context,
):

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM requests
        WHERE status = 'Yangi'
        ORDER BY id DESC
        LIMIT 50
        """
    ).fetchall()

    conn.close()

    if not rows:

        await update.message.reply_text(
            "📋 Hozircha yangi so'rovlar yo'q."
        )

        return

    for row in rows:

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ TASDIQLASH",
                        callback_data=
                        f"manager_approve:{row['id']}",
                    ),
                    InlineKeyboardButton(
                        "❌ BEKOR QILISH",
                        callback_data=
                        f"manager_cancel:{row['id']}",
                    ),
                ]
            ]
        )

        await update.message.reply_text(
            request_text(row),
            parse_mode="HTML",
            reply_markup=keyboard,
        )


# ============================================================
# MANAGER TASDIQLASH
# ============================================================

async def manager_approve(
    update,
    context,
    request_id,
):

    query = update.callback_query

    await query.answer()

    row = get_request(
        request_id
    )

    if not row:
        return

    if row["status"] != "Yangi":

        await query.answer(
            "Bu so'rov allaqachon ko'rib chiqilgan.",
            show_alert=True,
        )

        return

    manager_row = get_employee_by_telegram(
        query.from_user.id
    )

    if not manager_row:
        return

    manager = employee_data(
        manager_row
    )

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = db()

    conn.execute(
        """
        UPDATE requests
        SET status = 'Manager tasdiqladi',
            manager_id = ?,
            manager_name = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            manager["id"],
            manager["name"],
            now,
            request_id,
        ),
    )

    conn.commit()
    conn.close()

    await query.edit_message_reply_markup(
        reply_markup=None
    )

    await query.message.reply_text(
        f"✅ So'rov №{request_id} tasdiqlandi."
    )

    await send_to_operators(
        context,
        request_id,
    )


# ============================================================
# MANAGER BEKOR
# ============================================================

async def manager_cancel(
    update,
    context,
    request_id,
):

    query = update.callback_query

    await query.answer()

    context.user_data[
        "cancel_request_id"
    ] = request_id

    context.user_data[
        "cancel_type"
    ] = "manager"

    await query.message.reply_text(
        f"❌ So'rov №{request_id} "
        "uchun bekor qilish sababini yozing:"
    )


# ============================================================
# MANAGER BEKOR SABABI
# ============================================================

async def manager_cancel_reason(
    update,
    context,
):

    request_id = context.user_data.get(
        "cancel_request_id"
    )

    reason = update.message.text.strip()

    if not request_id:
        return

    manager_row = get_employee_by_telegram(
        update.effective_user.id
    )

    manager = employee_data(
        manager_row
    )

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = db()

    conn.execute(
        """
        UPDATE requests
        SET status = 'Manager bekor qildi',
            manager_id = ?,
            manager_name = ?,
            manager_comment = ?,
            updated_at = ?
        WHERE id = ?
        AND status = 'Yangi'
        """,
        (
            manager["id"],
            manager["name"],
            reason,
            now,
            request_id,
        ),
    )

    conn.commit()
    conn.close()

    row = get_request(
        request_id
    )

    context.user_data.clear()

    await update.message.reply_text(
        f"❌ So'rov №{request_id} bekor qilindi.\n\n"
        f"💬 Sabab: {reason}",
        reply_markup=manager_menu(),
    )

    if row:

        try:

            await context.bot.send_message(
                chat_id=row["telegram_id"],
                text=(
                    f"❌ <b>So'rovingiz bekor qilindi</b>\n\n"
                    f"🆔 So'rov №{request_id}\n"
                    f"🏪 Do'kon: {row['store_code']}\n"
                    f"💬 Sabab: {reason}"
                ),
                parse_mode="HTML",
            )

        except Exception:
            pass


# ============================================================
# OPERATORGA YUBORISH
# ============================================================

async def send_to_operators(
    context,
    request_id,
):

    row = get_request(
        request_id
    )

    if not row:
        return

    text = request_text(
        row,
        "📋 DOSTAVKA SO‘ROVI",
    )

    text += (
        f"\n👤 Manager: "
        f"{row['manager_name'] or '-'}\n"
        f"📌 Holat: Manager tomonidan tasdiqlandi"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ BAJARILDI",
                    callback_data=
                    f"operator_done:{request_id}",
                ),
                InlineKeyboardButton(
                    "❌ BEKOR QILINDI",
                    callback_data=
                    f"operator_cancel:{request_id}",
                ),
            ]
        ]
    )

    for telegram_id in get_role_telegram_ids(
        "operator"
    ):

        try:

            await context.bot.send_message(
                chat_id=telegram_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        except Exception as e:

            logger.error(
                f"Operatorga xato: {e}"
            )


# ============================================================
# OPERATOR SO'ROVLARI
# ============================================================

async def operator_requests(
    update,
    context,
):

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM requests
        WHERE status = 'Manager tasdiqladi'
        ORDER BY id DESC
        LIMIT 50
        """
    ).fetchall()

    conn.close()

    if not rows:

        await update.message.reply_text(
            "📋 Hozircha bajarilishi kerak "
            "bo'lgan so'rovlar yo'q."
        )

        return

    for row in rows:

        text = request_text(
            row,
            "📋 DOSTAVKA SO‘ROVI",
        )

        text += (
            f"\n👤 Manager: "
            f"{row['manager_name'] or '-'}\n"
            f"📌 Holat: Manager tomonidan tasdiqlandi"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ BAJARILDI",
                        callback_data=
                        f"operator_done:{row['id']}",
                    ),
                    InlineKeyboardButton(
                        "❌ BEKOR QILINDI",
                        callback_data=
                        f"operator_cancel:{row['id']}",
                    ),
                ]
            ]
        )

        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )


# ============================================================
# OPERATOR BAJARDI
# ============================================================

async def operator_done(
    update,
    context,
    request_id,
):

    query = update.callback_query

    await query.answer()

    row = get_request(
        request_id
    )

    if not row:
        return

    if row["status"] != "Manager tasdiqladi":

        await query.answer(
            "Bu so'rov allaqachon ko'rib chiqilgan.",
            show_alert=True,
        )

        return

    store_structure = get_store_structure()

    code_col = store_structure["code"]
    delivery_col = store_structure["delivery"]

    conn = db()

    # DO'KON DASTAVKA KODINI O'ZGARTIRISH
    rows = conn.execute(
        "SELECT rowid, * FROM stores"
    ).fetchall()

    for store_row in rows:

        current_code = normalize_code(
            store_row[code_col]
        )

        if current_code == normalize_code(
            row["store_code"]
        ):

            conn.execute(
                f"""
                UPDATE stores
                SET {quote_identifier(delivery_col)} = ?
                WHERE rowid = ?
                """,
                (
                    row["new_delivery"],
                    store_row["rowid"],
                ),
            )

            break

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn.execute(
        """
        UPDATE requests
        SET status = 'Bajarildi',
            updated_at = ?
        WHERE id = ?
        """,
        (
            now,
            request_id,
        ),
    )

    conn.commit()
    conn.close()

    await query.edit_message_reply_markup(
        reply_markup=None
    )

    await query.message.reply_text(
        f"✅ So'rov №{request_id} bajarildi."
    )

    # DASTAVKAGA
    try:

        await context.bot.send_message(
            chat_id=row["telegram_id"],
            text=(
                f"✅ <b>So'rovingiz bajarildi!</b>\n\n"
                f"🆔 So'rov №{request_id}\n"
                f"🏪 Do'kon: {row['store_code']}\n"
                f"🏬 {row['store_name'] or '-'}\n"
                f"🚚 Eski yo'nalish: "
                f"{row['old_delivery'] or '-'}\n"
                f"➡️ Yangi yo'nalish: "
                f"{row['new_delivery']}"
            ),
            parse_mode="HTML",
        )

    except Exception:
        pass

    # MANAGERLAR
    for telegram_id in get_role_telegram_ids(
        "manager"
    ):

        try:

            await context.bot.send_message(
                chat_id=telegram_id,
                text=(
                    f"✅ <b>Dostavka so'rovi bajarildi</b>\n\n"
                    f"🆔 So'rov №{request_id}\n"
                    f"🏪 Do'kon: {row['store_code']}\n"
                    f"➡️ Yangi yo'nalish: "
                    f"{row['new_delivery']}\n"
                    f"👤 Dastavka: "
                    f"{row['employee_name']}"
                ),
                parse_mode="HTML",
            )

        except Exception:
            pass

    # NAZORATCHILAR
    for telegram_id in get_role_telegram_ids(
        "nazoratchi"
    ):

        try:

            await context.bot.send_message(
                chat_id=telegram_id,
                text=(
                    f"✅ <b>Dostavka o'zgarishi bajarildi</b>\n\n"
                    f"🆔 So'rov №{request_id}\n"
                    f"🏪 Do'kon: {row['store_code']}\n"
                    f"🏬 {row['store_name'] or '-'}\n"
                    f"🚚 Yangi dastavka: "
                    f"{row['new_delivery']}"
                ),
                parse_mode="HTML",
            )

        except Exception:
            pass


# ============================================================
# OPERATOR BEKOR
# ============================================================

async def operator_cancel(
    update,
    context,
    request_id,
):

    query = update.callback_query

    await query.answer()

    context.user_data[
        "cancel_request_id"
    ] = request_id

    context.user_data[
        "cancel_type"
    ] = "operator"

    await query.message.reply_text(
        f"❌ So'rov №{request_id} "
        "uchun bekor qilish sababini yozing:"
    )


async def operator_cancel_reason(
    update,
    context,
):

    request_id = context.user_data.get(
        "cancel_request_id"
    )

    reason = update.message.text.strip()

    if not request_id:
        return

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = db()

    conn.execute(
        """
        UPDATE requests
        SET status = 'Operator bekor qildi',
            operator_comment = ?,
            updated_at = ?
        WHERE id = ?
        AND status = 'Manager tasdiqladi'
        """,
        (
            reason,
            now,
            request_id,
        ),
    )

    conn.commit()
    conn.close()

    row = get_request(
        request_id
    )

    context.user_data.clear()

    await update.message.reply_text(
        f"❌ So'rov №{request_id} bekor qilindi.\n\n"
        f"💬 Sabab: {reason}",
        reply_markup=operator_menu(),
    )

    if row:

        try:

            await context.bot.send_message(
                chat_id=row["telegram_id"],
                text=(
                    f"❌ <b>So'rovingiz bekor qilindi</b>\n\n"
                    f"🆔 So'rov №{request_id}\n"
                    f"🏪 Do'kon: {row['store_code']}\n"
                    f"💬 Sabab: {reason}"
                ),
                parse_mode="HTML",
            )

        except Exception:
            pass


# ============================================================
# DASTAVKA SO'ROVLARI
# ============================================================

async def my_requests(
    update,
    context,
):

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM requests
        WHERE telegram_id = ?
        ORDER BY id DESC
        LIMIT 50
        """,
        (
            update.effective_user.id,
        ),
    ).fetchall()

    conn.close()

    if not rows:

        await update.message.reply_text(
            "📋 Sizda hozircha so'rovlar mavjud emas."
        )

        return

    for row in rows:

        await update.message.reply_text(
            f"📋 <b>So'rov №{row['id']}</b>\n\n"
            f"🏪 Do'kon: {row['store_code']}\n"
            f"🏬 Nomi: {row['store_name'] or '-'}\n"
            f"🚚 Eski: {row['old_delivery'] or '-'}\n"
            f"➡️ Yangi: {row['new_delivery'] or '-'}\n"
            f"💬 Sabab: {row['reason'] or '-'}\n"
            f"📌 Holat: <b>{row['status']}</b>",
            parse_mode="HTML",
        )


# ============================================================
# NAZORATCHI DO'KON QIDIRISH
# ============================================================

async def inspector_store_search(
    update,
    context,
):

    context.user_data[
        "mode"
    ] = "inspector_store"

    await update.message.reply_text(
        "🔎 Do'kon kodini yuboring:"
    )


# ============================================================
# NAZORATCHI SO'ROVLAR
# ============================================================

async def inspector_requests(
    update,
    context,
):

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM requests
        ORDER BY id DESC
        LIMIT 50
        """
    ).fetchall()

    conn.close()

    if not rows:

        await update.message.reply_text(
            "📋 Hozircha so'rovlar mavjud emas."
        )

        return

    for row in rows:

        await update.message.reply_text(
            f"📋 <b>So'rov №{row['id']}</b>\n\n"
            f"👤 Xodim: {row['employee_name'] or '-'}\n"
            f"🏪 Do'kon: {row['store_code'] or '-'}\n"
            f"🏬 Do'kon: {row['store_name'] or '-'}\n"
            f"📍 Region: {row['region'] or '-'}\n"
            f"🚚 Hozirgi: {row['old_delivery'] or '-'}\n"
            f"➡️ Yangi: {row['new_delivery'] or '-'}\n"
            f"💬 Izoh: {row['reason'] or '-'}\n"
            f"📌 Holat: <b>{row['status']}</b>",
            parse_mode="HTML",
        )


# ============================================================
# NAZORATCHI HISOBOT
# ============================================================

async def inspector_report(
    update,
    context,
):

    conn = db()

    stores = conn.execute(
        "SELECT COUNT(*) AS c FROM stores"
    ).fetchone()["c"]

    employees = conn.execute(
        "SELECT COUNT(*) AS c FROM employees"
    ).fetchone()["c"]

    requests = conn.execute(
        "SELECT COUNT(*) AS c FROM requests"
    ).fetchone()["c"]

    new = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM requests
        WHERE status = 'Yangi'
        """
    ).fetchone()["c"]

    approved = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM requests
        WHERE status = 'Manager tasdiqladi'
        """
    ).fetchone()["c"]

    completed = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM requests
        WHERE status = 'Bajarildi'
        """
    ).fetchone()["c"]

    cancelled = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM requests
        WHERE status IN (
            'Manager bekor qildi',
            'Operator bekor qildi'
        )
        """
    ).fetchone()["c"]

    conn.close()

    await update.message.reply_text(
        "📊 <b>HISOBOT</b>\n\n"
        f"🏪 Do'konlar: {stores}\n"
        f"👥 Xodimlar: {employees}\n"
        f"📋 Jami so'rovlar: {requests}\n\n"
        f"🆕 Yangi: {new}\n"
        f"👤 Manager tasdiqlagan: {approved}\n"
        f"✅ Bajarilgan: {completed}\n"
        f"❌ Bekor qilingan: {cancelled}",
        parse_mode="HTML",
    )


# ============================================================
# NAZORATCHI DASTAVKALAR
# ============================================================

async def inspector_deliveries(
    update,
    context,
):

    structure = get_store_structure()

    delivery_col = structure["delivery"]

    conn = db()

    rows = conn.execute(
        f"""
        SELECT
            {quote_identifier(delivery_col)} AS delivery,
            COUNT(*) AS count
        FROM stores
        WHERE {quote_identifier(delivery_col)}
        IS NOT NULL
        AND TRIM(
            {quote_identifier(delivery_col)}
        ) != ''
        GROUP BY {quote_identifier(delivery_col)}
        ORDER BY {quote_identifier(delivery_col)}
        """
    ).fetchall()

    conn.close()

    if not rows:

        await update.message.reply_text(
            "🚚 Dastavkalar topilmadi."
        )

        return

    text = "🚚 <b>DASTAVKALAR</b>\n\n"

    for row in rows:

        text += (
            f"🚚 {row['delivery']}"
            f" — {row['count']} ta do'kon\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
    )


# ============================================================
# CHIQISH
# ============================================================

async def logout(
    update,
    context,
):

    context.user_data.clear()

    await update.message.reply_text(
        "🚪 Tizimdan chiqdingiz.\n\n"
        "Qayta kirish uchun /start ni bosing."
    )


# ============================================================
# CALLBACK
# ============================================================

async def callback_handler(
    update,
    context,
):

    query = update.callback_query

    data = query.data

    if data.startswith(
        "manager_approve:"
    ):

        request_id = int(
            data.split(":")[1]
        )

        await manager_approve(
            update,
            context,
            request_id,
        )

        return

    if data.startswith(
        "manager_cancel:"
    ):

        request_id = int(
            data.split(":")[1]
        )

        await manager_cancel(
            update,
            context,
            request_id,
        )

        return

    if data.startswith(
        "operator_done:"
    ):

        request_id = int(
            data.split(":")[1]
        )

        await operator_done(
            update,
            context,
            request_id,
        )

        return

    if data.startswith(
        "operator_cancel:"
    ):

        request_id = int(
            data.split(":")[1]
        )

        await operator_cancel(
            update,
            context,
            request_id,
        )

        return


# ============================================================
# ASOSIY MESSAGE HANDLER
# ============================================================

async def message_handler(
    update,
    context,
):

    if not update.message:
        return

    text = update.message.text.strip()

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    if context.user_data.get(
        "awaiting_login"
    ):

        await login(
            update,
            context,
        )

        return

    # --------------------------------------------------------
    # XODIM
    # --------------------------------------------------------

    row = get_employee_by_telegram(
        update.effective_user.id
    )

    if not row:

        context.user_data[
            "awaiting_login"
        ] = True

        await update.message.reply_text(
            "❗ Siz tizimga kirmagansiz.\n\n"
            "Xodim ID raqamingizni yuboring."
        )

        return

    employee = employee_data(row)

    role = parse_role(
        employee["position"]
    )

    # --------------------------------------------------------
    # BEKOR QILISH SABABI
    # --------------------------------------------------------

    if context.user_data.get(
        "cancel_type"
    ) == "manager":

        await manager_cancel_reason(
            update,
            context,
        )

        return

    if context.user_data.get(
        "cancel_type"
    ) == "operator":

        await operator_cancel_reason(
            update,
            context,
        )

        return

    mode = context.user_data.get(
        "mode"
    )

    # ========================================================
    # DASTAVKA
    # ========================================================

    if role == "dastavka":

        if text == "🔎 Do'kon qidirish":

            await store_search_start(
                update,
                context,
            )

            return

        if text == "✏️ O'zgartirish kiritish":

            await change_start(
                update,
                context,
            )

            return

        if text == "📋 Mening so'rovlarim":

            await my_requests(
                update,
                context,
            )

            return

        if text == "👤 Mening ma'lumotlarim":

            await update.message.reply_text(
                employee_info_text(employee),
                parse_mode="HTML",
            )

            return

        if text == "🚪 Chiqish":

            await logout(
                update,
                context,
            )

            return

        if mode == "store_search":

            await store_search_handle(
                update,
                context,
            )

            return

        if mode == "change_store":

            await change_store_handle(
                update,
                context,
            )

            return

        if mode == "change_delivery":

            await change_delivery_handle(
                update,
                context,
            )

            return

        if mode == "change_reason":

            await change_reason_handle(
                update,
                context,
            )

            return

    # ========================================================
    # MANAGER
    # ========================================================

    if role == "manager":

        if text == "📋 So'rovlar":

            await manager_requests(
                update,
                context,
            )

            return

        if text == "👤 Mening ma'lumotlarim":

            await update.message.reply_text(
                employee_info_text(employee),
                parse_mode="HTML",
            )

            return

        if text == "🚪 Chiqish":

            await logout(
                update,
                context,
            )

            return

    # ========================================================
    # OPERATOR
    # ========================================================

    if role == "operator":

        if text == "📋 So'rovlar":

            await operator_requests(
                update,
                context,
            )

            return

        if text == "👤 Mening ma'lumotlarim":

            await update.message.reply_text(
                employee_info_text(employee),
                parse_mode="HTML",
            )

            return

        if text == "🚪 Chiqish":

            await logout(
                update,
                context,
            )

            return

    # ========================================================
    # NAZORATCHI
    # ========================================================

    if role == "nazoratchi":

        if text == "🔎 Do'kon qidirish":

            await inspector_store_search(
                update,
                context,
            )

            return

        if text == "📋 So'rovlar":

            await inspector_requests(
                update,
                context,
            )

            return

        if text == "📊 Hisobot":

            await inspector_report(
                update,
                context,
            )

            return

        if text == "🚚 Dastavkalar":

            await inspector_deliveries(
                update,
                context,
            )

            return

        if text == "👤 Mening ma'lumotlarim":

            await update.message.reply_text(
                employee_info_text(employee),
                parse_mode="HTML",
            )

            return

        if text == "🚪 Chiqish":

            await logout(
                update,
                context,
            )

            return

        if mode == "inspector_store":

            store = get_store(text)

            if not store:

                await update.message.reply_text(
                    "❌ Bunday do'kon topilmadi."
                )

                return

            await update.message.reply_text(
                store_text(store),
                parse_mode="HTML",
            )

            context.user_data["mode"] = None

            return


# ============================================================
# ERROR
# ============================================================

async def error_handler(
    update,
    context,
):

    logger.error(
        "Bot xatosi:",
        exc_info=context.error,
    )


# ============================================================
# DIAGNOSTIKA
# ============================================================

def diagnostic():

    print()
    print("=" * 60)
    print("DATABASE TEKSHIRILMOQDA")
    print("=" * 60)

    print()
    print("📁 Baza:")
    print(DB_FILE)

    print()
    print("👥 EMPLOYEES USTUNLARI:")

    employee_structure = (
        get_employee_structure()
    )

    for column in employee_structure[
        "columns"
    ]:

        print(
            f"   - {column}"
        )

    print()
    print("🔎 ANIQLANGAN XODIM USTUNLARI:")

    print(
        "   ID:",
        employee_structure["id"],
    )

    print(
        "   ISM:",
        employee_structure["name"],
    )

    print(
        "   LAVOZIM:",
        employee_structure["position"],
    )

    print(
        "   DASTAVKA:",
        employee_structure["delivery"],
    )

    print()
    print("🏪 STORES USTUNLARI:")

    store_structure = (
        get_store_structure()
    )

    for column in store_structure[
        "columns"
    ]:

        print(
            f"   - {column}"
        )

    print()
    print("🔎 ANIQLANGAN DO'KON USTUNLARI:")

    print(
        "   KOD:",
        store_structure["code"],
    )

    print(
        "   NOMI:",
        store_structure["name"],
    )

    print(
        "   REGION:",
        store_structure["region"],
    )

    print(
        "   DASTAVKA:",
        store_structure["delivery"],
    )

    conn = db()

    employee_count = conn.execute(
        "SELECT COUNT(*) AS c FROM employees"
    ).fetchone()["c"]

    store_count = conn.execute(
        "SELECT COUNT(*) AS c FROM stores"
    ).fetchone()["c"]

    request_count = conn.execute(
        "SELECT COUNT(*) AS c FROM requests"
    ).fetchone()["c"]

    conn.close()

    print()
    print(
        f"👥 Xodimlar: {employee_count}"
    )

    print(
        f"🏪 Do'konlar: {store_count}"
    )

    print(
        f"📋 So'rovlar: {request_count}"
    )

    # 498 test
    test = get_employee_by_id("498")

    print()

    if test:

        employee = employee_data(test)

        print(
            "✅ TEST: 498 ID TOPILDI"
        )

        print(
            f"   Ism: {employee['name']}"
        )

        print(
            f"   Lavozim: {employee['position']}"
        )

        print(
            f"   Dastavka: {employee['delivery']}"
        )

    else:

        print(
            "⚠️ TEST: 498 ID topilmadi"
        )

    print()
    print("=" * 60)
    print()


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print("🤖 TELEGRAM BOT")
    print("=" * 60)

    if not DB_FILE.exists():

        print()
        print(
            "❌ baza.db topilmadi!"
        )

        print(
            DB_FILE
        )

        return

    try:

        prepare_database()

        diagnostic()

    except Exception as e:

        print()
        print(
            "❌ DATABASE XATOSI:"
        )

        print(e)

        return

    if (
        TOKEN
        == "BU_YERGA_YANGI_BOT_TOKENINGIZNI_QOYING"
    ):

        print()
        print(
            "❌ TOKEN KIRITILMAGAN!"
        )

        print()
        print(
            "bot.py ichidagi TOKEN "
            "joyiga yangi tokenni qo'ying."
        )

        return

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            message_handler,
        )
    )

    application.add_error_handler(
        error_handler
    )

    print()
    print("=" * 60)
    print("✅ BOT ISHGA TUSHMOQDA")
    print("=" * 60)
    print()
    print(
        "Telegram orqali botni tekshiring."
    )
    print()

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()