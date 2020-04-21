from telegram import (
    InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
)

from telegram.ext import (
    Updater, Filters, CommandHandler, MessageHandler,
    InlineQueryHandler, CallbackQueryHandler, ConversationHandler
)

from telegram.error import (
    TelegramError, Unauthorized, BadRequest, TimedOut,
    ChatMigrated, NetworkError
)

import logging
logging.basicConfig(
    format='%(asctime)s - %(name)s %(levelname)s - %(message)s',
    level=logging.WARN
)

import requests
from emoji import emojize

from config.settings import TELEGRAM_BOT_TOKEN, COVID19_DATA_URL
from utils.menu_utils import build_menu


updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)

MENU_INFO, CHOOSE_UF, ALL_UFS, CHOOSE_CITY = range(4)


def start(update, context):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Olá, tudo bem?\nSou o COVID Bot e posso lhe informar sobre os números da pandemia de COVID-19 no Brasil.\nDigite */ajuda* para saber mais",
            parse_mode=ParseMode.MARKDOWN
    )


def info_help(update, context):
    text = "Digite */casos* para buscar informações sobre a COVID-19 no Brasil e veja dados:\n"
    text += "- De todos os estados\n"
    text += "- De um estado\n"
    text += "- De uma cidade específica"

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=ParseMode.MARKDOWN
    )


def unknown_commands(update, context):
    """ Exibe uma mensagem caso algum comando seja desconhecido """

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Não entendi este comando. Digite */ajuda* para ver todos os comandos",
        parse_mode=ParseMode.MARKDOWN
    )


def get_data(place_type, uf=None, city=None):
    """ Busca os dados da API """

    payload = {
        'is_last': 'True',
        'place_type': place_type
    }

    if uf is not None:
        payload.update({'state': uf})

    if city is not None:
        payload.update({'city': city})

    return requests.get(COVID19_DATA_URL, params=payload).json()


def show_info(update, context, data):
    """ Envia mensagens com base nas informações recebidas """

    if data.get('count') == 0:

        if update.callback_query is None:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Desculpe. Não encontrei dados da cidade de {update.message.text}. Veja se o nome da cidade está certo"
            )
        else:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Desculpe. Não encontrei dados de {update.callback_query.data}."
            )

        return

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Pronto, aqui estão as informações:"
    )

    for info in format_data(data):
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=info,
            parse_mode=ParseMode.MARKDOWN
        )


def format_data(data):
    """ Formata os dados em um padrão para exibir nas mensagens """

    formatted_messages = list()

    for info in data['results']:
        message = "Em *{}*:\n\n"
        message += "{} {} casos confirmados\n{} {} " + ('mortes' if info['deaths'] > 1 else 'morte') + "\n"
        message += "{} {}% de mortalidade\n\n{} *dados de {}*"

        formatted_messages.append(
            message.format(
                info['city'] if info['city'] is not None else info['state'],

                emojize(":warning:"), info['confirmed'],

                emojize(":skull:"), info['deaths'],

                emojize(":bar_chart:"), "{:.3}".format(info['death_rate'] * 100),

                emojize(":calendar:"), "/".join(info['date'].split('-')[::-1])
            )
        )

    return formatted_messages


def cases(update, context):
    """ Exibe as opções para as informações a serem buscadas """

    opt_keyboard = [
        [InlineKeyboardButton('De todos os estados', callback_data='all_ufs')],
        [InlineKeyboardButton('Escolher um estado', callback_data='choose_uf')],
        [InlineKeyboardButton('Escolher uma cidade', callback_data='choose_city')]
    ]

    update.message.reply_text(
        'Como gostaria de ver os dados?',
        reply_markup=InlineKeyboardMarkup(opt_keyboard, one_time_keyboard=True)
    )

    return MENU_INFO


def quit_conversation(update, context):
    """ Termina a conversa com o bot """

    logging.info(f'Usuário {update.effective_user.full_name} terminou a conversa')

    update.message.reply_text(
        text="OK. Digite */ajuda* para exibir outros comandos",
        parse_mode=ParseMode.MARKDOWN
    )

    return ConversationHandler.END


def handle_menu(update, context):
    """ Verica qual opção o usuário clicou no menu e executa as ações respectivas """

    query = update.callback_query
    query.answer()

    if query.data == 'all_ufs':
        query.edit_message_text(
            text="Certo! Irei buscar os dados. Aguarde um momento...",
            reply_markup=InlineKeyboardMarkup(
                build_menu([InlineKeyboardButton('OK', callback_data='todos os estados')], n_cols=1),
                one_time_keyboard=True
            )
        )

        return ALL_UFS

    elif query.data == 'choose_city':
        query.edit_message_text(text="Digite o nome da cidade, fazendo a distinção de maiúsculas, minúsculas e acentuação:")

        return CHOOSE_CITY

    elif query.data == 'choose_uf':
        uf_list = ['AC', 'AM', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG',
        'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO']

        uf_buttons = [InlineKeyboardButton(uf, callback_data=uf) for uf in uf_list]

        query.edit_message_text(
            text="Escolha o estado",
            reply_markup=InlineKeyboardMarkup(build_menu(uf_buttons, n_cols=5), one_time_keyboard=True)
        )

        return CHOOSE_UF

def handle_choose_city(update, context):
    """ Buscar dados de uma cidade """

    city = update.message.text
    
    update.message.reply_text(f'Certo. Irei buscar dados da cidade de {city}. Aguarde um momento...')

    data = get_data(place_type='city', city=city)

    show_info(update, context, data)

    return MENU_INFO


def handle_all_ufs(update, context):
    """ Buscar dados de todos os estados """

    query = update.callback_query
    query.answer()

    query.edit_message_text(
        text=f"Buscando dados de {query.data}..."
    )

    data = get_data(place_type='state')

    show_info(update, context, data)

    return MENU_INFO


def handle_choose_uf(update, context):
    """ Trata as ações dos botões """

    query = update.callback_query
    query.answer()

    query.edit_message_text(
        text=f"Certo! Buscando dados de {query.data}..."
    )

    data = get_data(place_type='state', uf=query.data)

    show_info(update, context, data)

    return MENU_INFO


def error_callback(update, context):
    """ Trata os possíveis erros durante a troca de mensagens """

    try:
        raise context.error
    except Unauthorized as u:
        # remover update.message.chat_id da conversation list
        logging.warn(f'Unauthorized {u}')
    except BadRequest as br:
        # trata requests mal formadas
        logging.warn(f'BadRequest {br}')
    except TimedOut as to:
        # trata conexões lentas que podem causar erro de timeout
        logging.warn(f'TimedOut {to}')
    except NetworkError as ne:
        # trata outros problemas de conexão
        logging.warn(f'NetworkError {ne}')
    except ChatMigrated as cme:
        # se o chat_id de um grupo mudou, use e.new_chat_id
        logging.warn(f'ChatMigratedError {cme}')
    except TelegramError as te:
        # trata outros problemas relacionados do Telegram
        logging.warn(f'TelegramError {te}')


def main():
    dispatcher = updater.dispatcher

    dispatcher.add_error_handler(error_callback)

    cases_handler = CommandHandler('casos', cases)
    info_help_handler = CommandHandler('ajuda', info_help)

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(info_help_handler)
    dispatcher.add_handler(ConversationHandler(
        entry_points=[cases_handler],

        states={
            MENU_INFO: [CallbackQueryHandler(handle_menu)],
            CHOOSE_UF: [CallbackQueryHandler(handle_choose_uf)],
            ALL_UFS: [CallbackQueryHandler(handle_all_ufs)],
            CHOOSE_CITY: [MessageHandler(Filters.regex(r"^[A-Za-záàâãéèêíïóôõöúçñÁÀÂÃÉÈÍÏÓÔÕÖÚÇÑ ]+$"),
                handle_choose_city)]
        },

        fallbacks=[CommandHandler('sair', quit_conversation),
        info_help_handler, cases_handler],
    ))
    dispatcher.add_handler(MessageHandler(Filters.command, unknown_commands))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
