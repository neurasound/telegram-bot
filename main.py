import os
from pathlib import Path
import logging
from typing import Dict

from telegram import ReplyKeyboardMarkup, Update, ReplyKeyboardRemove
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)
import json
import boto3
import argparse

def start_bot(API_KEY, S3_BUCKET=None, S3_PARENT_PATH=None, root_dir='/home/ubuntu/telegram_bot'):
    #Setup S3
    if S3_BUCKET is not None:
        s3_client = boto3.client('s3')

    # Enable logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
    )

    logger = logging.getLogger(__name__)

    CHOOSING, TYPING_REPLY, TYPING_CHOICE, RECORD, FRASES, FIN = range(6)

    reply_keyboard = [
        ['Edad', 'Sexo'],
        ['País', 'Provincia'],
        ['Listo'],
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    reply_keyboard0=[['Sí'],['No']]
    markup0 = ReplyKeyboardMarkup(reply_keyboard0, one_time_keyboard=True)

    reply_keyboard1=[['Continuar'],['Cancelar']]
    markup1 = ReplyKeyboardMarkup(reply_keyboard1, one_time_keyboard=True)

    reply_keyboard2=[['Siguiente'],['Repetir']]
    markup2 = ReplyKeyboardMarkup(reply_keyboard2, one_time_keyboard=True)

    def read_user_id(update: Update):
        
        global user_basic_data
        
        first_name=update.message.chat['first_name']
        user_id=update.message.chat['id']
        consentimiento = str(update.message.text)
        user_basic_data = {
            'first_name': first_name,
            'user_id': user_id,
            'consent': consentimiento
        }

    def facts_to_str(user_data: Dict[str, str]) -> str:
        """Helper function for formatting the gathered user info."""
        facts = [f'{key} - {value}' for key, value in user_data.items()]
        print(user_data.items) 
        
        return "\n".join(facts).join(['\n', '\n'])

    def respuestas(input_text,update: Update, context: CallbackContext) -> int:
    
        if input_text=='sí':
            global dict_answers
            dict_answers={}
            #Se lee el id de usuario y se almacena en un json
            user_id=read_user_id(update)
            
            #Continuamos con la recolección de datos
            update.message.reply_text('Buenísimo, arrancamos')
            update.message.reply_text('Completá los campos y al finalizar presioná "Listo"',
            reply_markup=markup,
            )
        elif input_text=='no':
            update.message.reply_text('Malardo, seguro?')

    def handle_message(update: Update, context: CallbackContext) -> int:
        text=str(update.message.text).lower()
        respuesta=respuestas(text,update,context)
        #update.message.reply_text(respuesta)

    def start(update: Update, context: CallbackContext) -> int:
        
        global first_name
        global frases,counter_frases
        with open(root_dir+'/lista_bot.txt','r') as lines:
            frases=lines.read().splitlines()    
        
        counter_frases=0
        first_name=update.message.chat['first_name']
        """Start the conversation and ask user for input."""
        update.message.reply_text(f'Hola {first_name}, gracias por ayudarnos a desarrollar nuestro producto')
        update.message.reply_text('Antes de comenzar, te vamos a solicitar algunos datos personales. Continuamos?',
        reply_markup=markup0)    

        return CHOOSING


    def regular_choice(update: Update, context: CallbackContext) -> int:
        """Ask the user for info about the selected predefined choice."""
        text = update.message.text
        context.user_data['choice'] = text
        update.message.reply_text(f'Por favor, completá tu {text.lower()}')

        return TYPING_REPLY


    def received_information(update: Update, context: CallbackContext) -> int:
        
        """Store info provided by user and ask for the next category."""
        
        user_data = context.user_data
        text = update.message.text
        category = user_data['choice']  
        user_data[category] = text
        dict_answers[category]=text
        del user_data['choice']

        update.message.reply_text('Gracias. Por favor, completá el siguiente campo o presioná "Listo" al finalizar',
                                reply_markup=markup)    

        return CHOOSING

    def record(update: Update, context: CallbackContext) -> int:
    
        update.message.reply_text('Te pedimos que nos envíes un mensaje de voz leyendo cada una de las frases que te vamos a enviar. Por favor, tratá de hacerlo en un ambiente silencioso')
        update.message.reply_text('('+str(counter_frases+1)+'/'+str(len(frases))+') Leer la siguiente frase:\n\n'+'"'+frases[counter_frases]+'"')
        
        return FRASES

    def cancelar(update: Update, context: CallbackContext) -> int:
        update.message.reply_text('se cancela todo')
    
        return ConversationHandler.END

    def print_frases (update: Update, context: CallbackContext) -> int:
        
        global counter_frases, frases
        
        if counter_frases<=len(frases)-2:
        update.message.reply_text('continuamos...')    
        counter_frases+=1
        update.message.reply_text('('+str(counter_frases+1)+'/'+str(len(frases))+') Leer la siguiente frase:\n\n'+'"'+frases[counter_frases]+'"')
        else:
        Path(root_dir,user_basic_data['user_id'],'audio_data').rmdir()
        Path(root_dir,user_basic_data['user_id']).rmdir()
        update.message.reply_text('Eso es todo. Muchas gracias por brindarnos tu ayuda y tu tiempo!')
        return ConversationHandler.END

    def voice_handler(update: Update, context: CallbackContext) -> int:
        
        print(user_dir)
        bot = context.bot
        file = bot.getFile(update.message.voice.file_id)
        
        user_audio_path=os.path.join(user_dir,'audio_data')
        
        if not os.path.exists(user_audio_path):
        os.mkdir(user_audio_path)  
        
        local_path = os.path.join(user_audio_path,str(user_basic_data['user_id'])+'_'+str(counter_frases+1)+'.mp3')
        file.download(local_path)
        if S3_BUCKET is not None:
            s3_client.upload_file(local_path,S3_BUCKET,S3_PARENT_PATH + '/{}/{}'.format(str(user_basic_data['user_id']),str(user_basic_data['user_id'])+'_'+str(counter_frases+1)+'.mp3'))
            Path(local_path).unlink()
        update.message.reply_text('Si estás conforme con tu grabación, presioná "siguiente", sino presioná "repetir"',reply_markup=markup2) 


    def repeat_audio (update: Update, context: CallbackContext) -> int:

        update.message.reply_text('Repetí tu audio')

    def done(update: Update, context: CallbackContext) -> int:
        
        global user_dir

        """Display the gathered info and end the conversation."""
        user_data = context.user_data
        if 'choice' in user_data:
            del user_data['choice']
        resumen=facts_to_str(user_data)
        update.message.reply_text(f"Datos de usuario: {resumen}",
            reply_markup=ReplyKeyboardRemove(),
        )
        
        update.message.reply_text('Ahora te pediremos que nos envíes algunos mensajes de voz', reply_markup=markup1)

        user_basic_data.update(dict_answers)
        user_id=str(user_basic_data['user_id'])
        
        user_dir=os.path.join(root_dir,user_id)

        if not os.path.exists(user_dir):
        os.mkdir(user_dir)  

        local_text_path = user_dir+'/UserData_'+user_id+'.txt'
        text_file = open(local_text_path, 'w')    
        text_file.write(json.dumps(user_basic_data))
        text_file.close()

        if S3_BUCKET is not None:
            s3_client.upload_file(local_text_path,S3_BUCKET,S3_PARENT_PATH + '/{}/{}'.format(str(user_basic_data['user_id']),'UserData_'+user_id+'.txt'))
            Path(local_text_path).unlink()
        user_data.clear()
        
        return RECORD

    """Run the bot."""
    # Create the Updater and pass it your bot's token.
    updater= Updater(API_KEY,use_context=True)
    
    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [MessageHandler(Filters.regex('^(Edad|Sexo|País|Provincia)$'), regular_choice)],
            TYPING_CHOICE: [MessageHandler(Filters.text & ~(Filters.command | Filters.regex('^Listo$')), regular_choice)],
            TYPING_REPLY: [MessageHandler(Filters.text & ~(Filters.command | Filters.regex('^Listo$')),
                    received_information)],
            RECORD: [MessageHandler (Filters.regex('^Continuar$'), record)],
            FRASES: [MessageHandler (Filters.regex('^Siguiente$'), print_frases)],   
        },
        fallbacks=[MessageHandler(Filters.regex('^Listo$'), done), MessageHandler(Filters.regex('^Cancelar$'), cancelar),
                    MessageHandler(Filters.regex('^Repetir$'), repeat_audio)],
    )

    dp.add_handler(conv_handler)
    dp.add_handler(MessageHandler(Filters.text, handle_message))
    dp.add_handler(MessageHandler(Filters.voice, voice_handler))
    
    # Start the Bot
    updater.start_polling()
    
    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='Start telegram bot for data collection')
    argparser.add_argument('--api_key', help='Telegram API Key')
    argparser.add_argument('--s3_bucket', type=str, help='S3 bucket to store collected data')
    argparser.add_argument('--s3_path', type=str, help='S3 path where the data will be stored')
    argparser.add_argument('--root_dir', type=str, help='Local path where the list of phrases is located')
    args = vars(argparser.parse_args())
    start_bot(args['api_key'], args['s3_bucket'], args['s3_path'], args['root_dir'])