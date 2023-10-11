import logging
import requests
import sys, getopt

from telegram import *
from telegram.ext import *

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

routes = requests.get("https://data.etabus.gov.hk/v1/transport/kmb/route/").json()["data"]

async def start(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Welcome")

async def location_handler(update: Update, context: CallbackContext):
    user_location = update.message.location

    dest = context.user_data["dest"]
    bound = context.user_data["bound"]
    service_type = context.user_data["service_type"]
    route = context.user_data["route"]

    please_wait_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="請等等🙏🏻幫緊你！幫緊你！")

    route_stop_list = requests.get(f"https://data.etabus.gov.hk/v1/transport/kmb/route-stop/{route}/{bound}/{service_type}").json()["data"]

    nearest_stop = {}

    for route_stop in route_stop_list:
        stop_details = requests.get(f"https://data.etabus.gov.hk/v1/transport/kmb/stop/{route_stop['stop']}").json()["data"]

        distance = ((float(stop_details["lat"]) - user_location.latitude) ** 2 + (float(stop_details["long"]) - user_location.longitude) ** 2) ** 0.5
        
        try:
            if nearest_stop["distance"] >= distance:
                nearest_stop = stop_details
                nearest_stop["distance"] = distance
        except KeyError:
            nearest_stop = stop_details
            nearest_stop["distance"] = distance

    nearest_location = Location(longitude=float(nearest_stop["long"]), latitude=float(nearest_stop["lat"]))
    nearest_venue = Venue(location=nearest_location, title=f"最近的巴士站: {nearest_stop['name_tc']}", address="")

    # await context.bot.send_message(chat_id=update.effective_chat.id, text=f"最近的巴士站: {nearest_stop['name_tc']}")
    await context.bot.send_venue(chat_id=update.effective_chat.id, venue=nearest_venue)
    
    eta_list = requests.get(f"https://data.etabus.gov.hk/v1/transport/kmb/eta/{nearest_stop['stop']}/{route}/{service_type}").json()["data"]

    for eta in eta_list:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"預計到達時間:\n{eta['eta']}")


async def command_handler(update: Update, context: CallbackContext):
    route = update.message.text.split("/")[1].upper()

    found_route = list(filter(lambda x: x["route"] == route, routes))

    if len(found_route) > 0:
    
        route_keyboard = list(map(lambda x: [InlineKeyboardButton(f"{x['orig_tc']}➡️{x['dest_tc']}", callback_data=f"{x['orig_tc']}@{x['dest_tc']}@{x['bound']}@{x['service_type']}@{x['route']}")], found_route))
        

        reply_markup = InlineKeyboardMarkup(route_keyboard)
        
        await update.message.reply_text("Please choose your destination:", reply_markup=reply_markup)
    
    else:

        await update.message.reply_text("No Route is found")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    data = query.data.split("@")

    context.user_data["orig"] = data[0]
    context.user_data["dest"] = data[1]
    context.user_data["bound"] = "outbound" if data[2] == "O" else "inbound"
    context.user_data["service_type"] = data[3]
    context.user_data["route"] = data[4]

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    await query.edit_message_text(text=f"{data[0]}➡️{data[1]}")

    keyboard = [
        [
            KeyboardButton("Share Location", request_location=True)
        ]
    ]
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Please share your location", reply_markup = ReplyKeyboardMarkup(keyboard))


def main() -> None:
    """Run the bot."""
    token = ""
    opts, args = getopt.getopt(sys.argv[1:], "t:", [])
    for opt, arg in opts:
        if opt == "-t":
            token = arg
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.LOCATION, location_handler))
    application.add_handler(MessageHandler(filters.Regex('^/'), command_handler))
    application.add_handler(CallbackQueryHandler(button))
    # application.add_handler(CommandHandler("help", help_command))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
