import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 启用日志
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# 🛠️ 您的专属固定配置（已为您完全填妥）
BOT_TOKEN = "8852759311:AAF6CkyW4glz3mUU8jxip3SMTfcK65U9FSo"
ADMIN_ID = 5874944720
GW_URL = "https://yyn.win"
DB_FILE = "bot_data.db"  # 数据库文件，会自动在同目录下生成

# 💾 SQLite 数据库初始化
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 用户表：储存昵称、积分、最后签到日期
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0, last_sign TEXT)''')
    # 活跃度表：储存用户每日发言数
    cursor.execute('''CREATE TABLE IF NOT EXISTS activity 
                      (user_id INTEGER, date_str TEXT, msg_count INTEGER DEFAULT 0, 
                       PRIMARY KEY (user_id, date_str))''')
    conn.commit()
    conn.close()

init_db()

# 📊 统计活跃度与更新用户昵称
async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return
    user = update.message.from_user
    user_id = user.id
    name = user.full_name
    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 更新或插入用户信息
    cursor.execute("INSERT INTO users (user_id, name) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET name=?", (user_id, name, name))
    # 增加今日发言计数
    cursor.execute("INSERT INTO activity (user_id, date_str, msg_count) VALUES (?, ?, 1) ON CONFLICT(user_id, date_str) DO UPDATE SET msg_count = msg_count + 1", (user_id, today))
    
    conn.commit()
    conn.close()

# 📝 每日签到功能命令：/sign
async def sign_in(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_activity(update, context)
    user = update.message.from_user
    user_id = user.id
    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT points, last_sign FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    points = row[0] if row else 0
    last_sign = row[1] if row else ""

    if last_sign == today:
        await update.message.reply_text(f"❌ {user.full_name}，您今天已经签到过了，明天再来吧！")
    else:
        new_points = points + 10
        cursor.execute("UPDATE users SET points = ?, last_sign = ? WHERE user_id = ?", (new_points, today, user_id))
        conn.commit()
        await update.message.reply_text(f"✅ 签到成功！\n👤 账户：{user.full_name}\n💰 获得：10 积分\n🪙 总积分：{new_points}")
        
    conn.close()

# 🏆 活跃度排行榜计算逻辑
def get_ranking(days=1):
    now = datetime.now()
    target_dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 联合查询：统计指定日期内的发言总数，并关联用户昵称
    placeholders = ','.join('?' for _ in target_dates)
    query = f'''
        SELECT u.name, SUM(a.msg_count) as total 
        FROM activity a 
        JOIN users u ON a.user_id = u.user_id 
        WHERE a.date_str IN ({placeholders}) 
        GROUP BY a.user_id 
        ORDER BY total DESC 
        LIMIT 10
    '''
    cursor.execute(query, target_dates)
    ranking = cursor.fetchall()
    conn.close()
    return ranking

# 💬 排行榜指令群：/rank
async def show_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_activity(update, context)
    args = context.args
    days = 1
    title = "今日活跃排行 ⏰"
    
    if args and args.isdigit():
        days = int(args)
        title = f"最近 {days} 天活跃排行 📊"

    ranking = get_ranking(days)
    if not ranking:
        await update.message.reply_text("该周期内群内暂无发言数据（需通过指令互动才会记录）。")
        return

    text = f"🏆 **群组 {title}** 🏆\n\n"
    for idx, (name, count) in enumerate(ranking, 1):
        text += f"{idx}. {name} —— 发言 {count} 条\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# 🌐 官网功能命令：/gw
async def show_website(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await track_activity(update, context)
    await update.message.reply_text(f"我们的官方网站是：{GW_URL}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # 绑定所有群组专属斜杠命令
    app.add_handler(CommandHandler("sign", sign_in))
    app.add_handler(CommandHandler("gw", show_website))
    app.add_handler(CommandHandler("rank", show_rank))
    app.add_handler(CommandHandler("rank7", lambda u, c: (setattr(c, 'args', ['7']), show_rank(u, c))))
    app.add_handler(CommandHandler("rank30", lambda u, c: (setattr(c, 'args', ['30']), show_rank(u, c))))
    app.add_handler(MessageHandler(filters.COMMAND, track_activity))

    print("🤖 您的专属群组机器人已成功启动并在后台监听中...")
    app.run_polling()

if __name__ == '__main__':
    main()
