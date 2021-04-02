# -*- coding: utf-8 -*-
import logging
import yaml
import psutil
import subprocess
import os
import sqlite3
from datetime import datetime
from configparser import ConfigParser
from shutil import copyfile
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext
)

MENU, EDIT_COIN_LIST, EDIT_USER_CONFIG, DELETE_DB = range(4)


class BTBManagerTelegram:
    def __init__(self, root_path='./', from_yaml=True, token=None, user_id=None):
        self.root_path = root_path
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)

        if from_yaml:
            token, user_id = self.__get_token_from_yaml()
        

        updater = Updater(token)
        dispatcher = updater.dispatcher

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.__start, Filters.user(user_id=eval(user_id)))],
            states={
                MENU: [MessageHandler(Filters.regex('^(Begin|⚙️ Configurations|🔍 Check bot status|👛 Edit coin list|▶ Start trade bot|⏹ Stop trade bot|❌ Delete database|⚙ Edit user.cfg|📜 Read last log lines|💵 Current value|📈 Current ratios|⬅️ Back|Go back|OK)$'), self.__menu)],
                EDIT_COIN_LIST: [MessageHandler(Filters.regex('(.*?)'), self.__edit_coin)],
                EDIT_USER_CONFIG: [MessageHandler(Filters.regex('(.*?)'), self.__edit_user_config)],
                DELETE_DB: [MessageHandler(Filters.regex('^(⚠ Confirm|Go back)$'), self.__delete_db)]
            },
            fallbacks=[CommandHandler('cancel', self.__cancel)],
            per_user=True
        )

        dispatcher.add_handler(conv_handler)
        updater.start_polling()
        updater.idle()

    def __get_token_from_yaml(self):
        telegram_url = None
        yaml_file_path = f'{self.root_path}config/apprise.yml'
        with open(yaml_file_path) as f:
            parsed_urls = yaml.load(f, Loader=yaml.FullLoader)['urls']
            for url in parsed_urls:
                if url.startswith('tgram'):
                    telegram_url = url.split('//')[1]
        if not telegram_url:
            self.logger.error('ERROR: No telegram configuration was found in your apprise.yml file.\nAborting.')
            exit(-1)
        try:
            tok = telegram_url.split('/')[0]
            uid = telegram_url.split('/')[1]
        except:
            self.logger.error('ERROR: No user_id has been set in the yaml configuration, anyone would be able to control your bot.\nAborting.')
            exit(-1)
        return tok, uid


    def __start(self, update: Update, _: CallbackContext) -> int:
        self.logger.info('Started conversation.')

        keyboard = [['Begin']]
        message = f'Hi *{update.message.from_user.first_name}*\!\nWelcome to _Binace Trade Bot Manager Telegram_\.\n\nThis Telegram bot was developed by @lorcalhost\.\nFind out more about the project [here](https://github.com/lorcalhost/BTB-manager-telegram)\.'
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            one_time_keyboard=True,
            resize_keyboard=True
        )
        update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2',
            disable_web_page_preview=True
        )
        return MENU

    def __menu(self, update: Update, _: CallbackContext) -> int:
        self.logger.info(f'Menu selector. ({update.message.text})')

        keyboard = [
            ['💵 Current value', '📈 Current ratios'],
            ['🔍 Check bot status', '⚙️ Configurations']
        ]

        config_keyboard = [
            ['▶ Start trade bot', '⏹ Stop trade bot'],
            ['📜 Read last log lines', '❌ Delete database'],
            ['⚙ Edit user.cfg', '👛 Edit coin list'],
            ['⬅️ Back']
        ]

        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )

        reply_markup_config = ReplyKeyboardMarkup(
            config_keyboard,
            resize_keyboard=True
        )

        if update.message.text in ['Begin', '⬅️ Back']:
            message = 'Please select one of the options.'
            update.message.reply_text(
                message, 
                reply_markup=reply_markup
            )

        elif update.message.text in ['Go back', 'OK', '⚙️ Configurations']:
            message = 'Please select one of the options.'
            update.message.reply_text(
                message, 
                reply_markup=reply_markup_config
            )
            
        elif update.message.text == '🔍 Check bot status':
            update.message.reply_text(
                self.__btn_check_status(),
                reply_markup=reply_markup
            )

        elif update.message.text == '👛 Edit coin list':
            re = self.__btn_edit_coin()
            if re[1]:
                update.message.reply_text(
                    re[0],
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode='MarkdownV2'
                )
                return EDIT_COIN_LIST
            else:
                update.message.reply_text(
                    re[0],
                    reply_markup=reply_markup_config,
                    parse_mode='MarkdownV2'
                )

        elif update.message.text == '▶ Start trade bot':
            update.message.reply_text(
                self.__btn_start_bot(),
                reply_markup=reply_markup_config,
                parse_mode='MarkdownV2'
            )

        elif update.message.text == '⏹ Stop trade bot':
            update.message.reply_text(
                self.__btn_stop_bot(),
                reply_markup=reply_markup_config
            )

        elif update.message.text == '❌ Delete database':
            re = self.__btn_delete_db()
            if re[1]:
                kb = [['⚠ Confirm', 'Go back']]
                update.message.reply_text(
                    re[0],
                    reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
                    parse_mode='MarkdownV2'
                )
                return DELETE_DB
            else:
                update.message.reply_text(
                    re[0],
                    reply_markup=reply_markup_config,
                    parse_mode='MarkdownV2'
                )

        elif update.message.text == '⚙ Edit user.cfg':
            re = self.__btn_edit_user_cfg()
            if re[1]:
                update.message.reply_text(
                    re[0],
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode='MarkdownV2'
                )
                return EDIT_USER_CONFIG
            else:
                update.message.reply_text(
                    re[0],
                    reply_markup=reply_markup_config,
                    parse_mode='MarkdownV2'
                )

        elif update.message.text == '📜 Read last log lines':
            update.message.reply_text(
                self.__btn_read_log(),
                reply_markup=reply_markup_config,
                parse_mode='MarkdownV2'
            )

        elif update.message.text == '💵 Current value':
            for m in self.__btn_current_value():
                update.message.reply_text(
                    m,
                    reply_markup=reply_markup,
                    parse_mode='MarkdownV2'
                )
        elif update.message.text == '📈 Current ratios':
            for m in self.__btn_current_ratios():
                update.message.reply_text(
                    m,
                    reply_markup=reply_markup,
                    parse_mode='MarkdownV2'
                )

        return MENU

    def __edit_coin(self, update: Update, _: CallbackContext) -> int:
        self.logger.info(f'Editing coin list. ({update.message.text})')

        if update.message.text != '/stop':
            message = f'✔ Successfully edited coin list file to:\n\n```\n{update.message.text}\n```'.replace('.', '\.')
            coin_file_path = f'{self.root_path}supported_coin_list'
            try:
                copyfile(coin_file_path, f'{coin_file_path}.backup')
                with open(coin_file_path, 'w') as f:
                    f.write(update.message.text + '\n')
            except:
                message = '❌ Unable to edit coin list file\.'
        else:
            message = '👌 Exited without changes\.\nYour `supported_coin_list` file was *not* modified\.'

        keyboard = [['Go back']]
        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
        update.message.reply_text(
            message, 
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )

        return MENU

    def __edit_user_config(self, update: Update, _: CallbackContext) -> int:
        self.logger.info(f'Editing user configuration. ({update.message.text})')

        if update.message.text != '/stop':
            message = f'✔ Successfully edited user configuration file to:\n\n```\n{update.message.text}\n```'.replace('.', '\.')
            user_cfg_file_path = f'{self.root_path}user.cfg'
            try:
                copyfile(user_cfg_file_path, f'{user_cfg_file_path}.backup')
                with open(user_cfg_file_path, 'w') as f:
                    f.write(update.message.text + '\n\n\n')
            except:
                message = '❌ Unable to edit user configuration file\.'
        else:
            message = '👌 Exited without changes\.\nYour `user.cfg` file was *not* modified\.'

        keyboard = [['Go back']]
        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
        update.message.reply_text(
            message, 
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )

        return MENU

    def __delete_db(self, update: Update, _: CallbackContext) -> int:
        self.logger.info(f'Asking if the user really wants to delete the db. ({update.message.text})')

        if update.message.text != 'Go back':
            message = '✔ Successfully deleted database file\.'
            db_file_path = f'{self.root_path}data/crypto_trading.db'
            try:
                copyfile(db_file_path, f'{db_file_path}.backup')
                os.remove(db_file_path)
            except:
                message = '❌ Unable to delete database file\.'
        else:
            message = '👌 Exited without changes\.\nYour database was *not* deleted\.'

        keyboard = [['OK']]
        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
        update.message.reply_text(
            message, 
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )

        return MENU

    @staticmethod
    def __find_process():
        for p in psutil.process_iter():
            if 'binance_trade_bot' in p.name() or 'binance_trade_bot' in ' '.join(p.cmdline()):
                return True
        return False

    def __find_and_kill_process(self):
        try:
            for p in psutil.process_iter():
                if 'binance_trade_bot' in p.name() or 'binance_trade_bot' in ' '.join(p.cmdline()):
                    p.terminate()
                    p.wait()
        except Exception as e:
            self.logger.info(f'ERROR: {e}')

    @staticmethod
    def __4096_cutter(m_list):
        message = ['']
        index = 0
        for m in m_list:
            if len(message[index]) + len(m) <= 4096:
                message[index] += m
            else:
                message.append(m)
                index += 1
        return message

    def __btn_check_status(self):
        self.logger.info('Check status button pressed.')

        message = '⚠ Binance Trade Bot is not running.'
        if self.__find_process():
            message = '✔ Binance Trade Bot is running.'
        return  message

    def __btn_edit_coin(self):
        self.logger.info('Edit coin list button pressed.')

        message = '⚠ Please stop Binance Trade Bot before editing the coin list\.'
        edit = False
        coin_file_path = f'{self.root_path}supported_coin_list'
        if not self.__find_process():
            if os.path.exists(coin_file_path):
                with open(coin_file_path) as f:
                    message = f'Current coin list is:\n\n```\n{f.read()}\n```\n\n_*Please reply with a message containing the updated coin list*_.\n\nWrite /stop to stop editing and exit without changes.'.replace('.', '\.')
                    edit = True
            else:
                message = f'❌ Unable to find coin list file at `{coin_file_path}`.'.replace('.', '\.')
        return [message, edit]

    def __btn_start_bot(self):
        self.logger.info('Start bot button pressed.')

        message = '⚠ Binance Trade Bot is already running\.'
        if not self.__find_process():
            if os.path.exists(f'{self.root_path}binance_trade_bot/'):
                subprocess.call('$(which python3) -m binance_trade_bot &', shell=True)
                if not self.__find_process():
                    message = '❌ Unable to start Binance Trade Bot\.'
                else:
                    message = '✔ Binance Trade Bot successfully started\.'
            else:
                message = '❌ Unable to find _Binance Trade Bot_ installation in this directory\.\nMake sure the `BTBManagerTelegram.py` file is in the _Binance Trade Bot_ installation folder\.'
        return message

    def __btn_stop_bot(self):
        self.logger.info('Stop bot button pressed.')

        message = '⚠ Binance Trade Bot is not running.'
        if self.__find_process():
            self.__find_and_kill_process()
            if not self.__find_process():
                message = '✔ Successfully stopped the bot.'
            else:
                message = '❌ Unable to stop Binance Trade Bot.\n\nIf you are running the telegram bot on Windows make sure to run with administrator privileges.'
        return message

    def __btn_delete_db(self):
        self.logger.info('Delete database button pressed.')

        message = '⚠ Please stop Binance Trade Bot before deleting the database file\.'
        delete = False
        db_file_path = f'{self.root_path}data/crypto_trading.db'
        if not self.__find_process():
            if os.path.exists(db_file_path):
                message = 'Are you sure you want to delete the database file?'
                delete = True
            else:
                message = f'⚠ Unable to find database file at `{db_file_path}`.'.replace('.', '\.')
        return [message, delete]

    def __btn_edit_user_cfg(self):
        self.logger.info('Edit user configuration button pressed.')

        message = '⚠ Please stop Binance Trade Bot before editing user configuration file\.'
        edit = False
        user_cfg_file_path = f'{self.root_path}user.cfg'
        if not self.__find_process():
            if os.path.exists(user_cfg_file_path):
                with open(user_cfg_file_path) as f:
                    message = f'Current configuration file is:\n\n```\n{f.read()}\n```\n\n_*Please reply with a message containing the updated configuration*_.\n\nWrite /stop to stop editing and exit without changes.'.replace('.', '\.')
                    edit = True
            else:
                message = f'❌ Unable to find user configuration file at `{user_cfg_file_path}`.'.replace('.', '\.')
        return [message, edit]

    def __btn_read_log(self):
        self.logger.info('Read log button pressed.')

        log_file_path = f'{self.root_path}logs/crypto_trading.log'
        message = f'❌ Unable to find log file at `{log_file_path}`.'.replace('.', '\.')
        if os.path.exists(log_file_path):
            with open(log_file_path) as f:
                file_content = f.read().replace('.', '\.')[-4000:]
                message = f'Last *4000* characters in log file:\n\n```\n{file_content}\n```'
        return message

    def __btn_current_value(self):
        self.logger.info('Current value button pressed.')

        db_file_path = f'{self.root_path}data/crypto_trading.db'
        user_cfg_file_path = f'{self.root_path}user.cfg'
        message = [f'⚠ Unable to find database file at `{db_file_path}`\.']
        if os.path.exists(db_file_path):
            try:
                # Get bridge currency symbol
                with open(user_cfg_file_path) as cfg:
                    config = ConfigParser()
                    config.read_file(cfg)
                    bridge = config.get('binance_user_config', 'bridge')

                con = sqlite3.connect(db_file_path)
                cur = con.cursor()

                # Get current coin symbol
                try:
                    cur.execute('''SELECT alt_coin_id FROM trade_history ORDER BY datetime DESC LIMIT 1;''')
                    current_coin = cur.fetchone()[0]
                    if current_coin is None:
                        raise Exception()
                except:
                    con.close()
                    return [f'❌ Unable to fetch current coin from database\.']

                # Get balance, current coin price in USD, current coin price in BTC
                try:
                    cur.execute(f'''SELECT balance, usd_price, btc_price, datetime FROM 'coin_value' WHERE coin_id = '{current_coin}' ORDER BY datetime DESC LIMIT 1;''')
                    balance, usd_price, btc_price, last_update = cur.fetchone()
                    if balance is None: balance = 0
                    if usd_price is None: usd_price = 0
                    if btc_price is None: btc_price = 0
                    last_update = datetime.strptime(last_update, '%Y-%m-%d %H:%M:%S.%f')
                except:
                    con.close()
                    return [f'❌ Unable to fetch current coin information from database\.', f'⚠ If you tried using the `Current value` button during a trade please try again after the trade has been completed\.']

                # Generate message
                try:
                    m_list = [f'\nLast update: `{last_update.strftime("%d/%m/%Y %H:%M:%S")}`\n\n*Current coin {current_coin}:*\n\t\- Balance: `{round(balance, 6)}` {current_coin}\n\t\- Value in *USD*: `{round((balance * usd_price), 2)}` $\n\t\- Value in *BTC*: `{round((balance * btc_price), 6)}` BTC\n'.replace('.', '\.')]
                    message = self.__4096_cutter(m_list)
                    con.close()
                except:
                    con.close()
                    return [f'❌ Something went wrong, unable to generate value at this time\.']
            except:
                message = ['❌ Unable to perform actions on the database\.']
        return message
                
    def __btn_current_ratios(self):
        self.logger.info('Current ratios button pressed.')

        db_file_path = f'{self.root_path}data/crypto_trading.db'
        user_cfg_file_path = f'{self.root_path}user.cfg'
        message = [f'⚠ Unable to find database file at `{db_file_path}`\.']
        if os.path.exists(db_file_path):
            try:
                # Get bridge currency symbol
                with open(user_cfg_file_path) as cfg:
                    config = ConfigParser()
                    config.read_file(cfg)
                    bridge = config.get('binance_user_config', 'bridge')

                con = sqlite3.connect(db_file_path)
                cur = con.cursor()

                # Get current coin symbol
                try:
                    cur.execute('''SELECT alt_coin_id FROM trade_history ORDER BY datetime DESC LIMIT 1;''')
                    current_coin = cur.fetchone()[0]
                    if current_coin is None:
                        raise Exception()
                except:
                    con.close()
                    return [f'❌ Unable to fetch current coin from database\.']

                # Get prices and ratios of all alt coins
                try:
                    cur.execute(f'''SELECT sh.datetime, p.to_coin_id, sh.other_coin_price, ( ( ( current_coin_price / other_coin_price ) - 0.001 * 5 * ( current_coin_price / other_coin_price ) ) - sh.target_ratio ) AS 'ratio_dict' FROM scout_history sh JOIN pairs p ON p.id = sh.pair_id WHERE p.from_coin_id='{current_coin}' AND p.from_coin_id = ( SELECT alt_coin_id FROM trade_history ORDER BY datetime DESC LIMIT 1) ORDER BY sh.datetime DESC LIMIT ( SELECT count(DISTINCT pairs.to_coin_id) FROM pairs WHERE pairs.from_coin_id='{current_coin}');''')
                    query = cur.fetchall()

                    # Generate message
                    last_update = datetime.strptime(query[0][0], '%Y-%m-%d %H:%M:%S.%f')
                    query = sorted(query, key=lambda k: k[-1], reverse=True)

                    m_list = [f'\nLast update: `{last_update.strftime("%d/%m/%Y %H:%M:%S")}`\n\n*Coin ratios compared to {current_coin}:*\n'.replace('.', '\.')]
                    for coin in query:
                        m_list.append(f'{coin[1]}:\n\t\- Price: `{coin[2]}` {bridge}\n\t\- Ratio: `{round(coin[3], 6)}`\n\n'.replace('.', '\.'))
                    
                    message = self.__4096_cutter(m_list)
                    con.close()
                except:
                    con.close()
                    return [f'❌ Something went wrong, unable to generate ratios at this time\.']
            except:
                message = ['❌ Unable to perform actions on the database\.']
        return message


    def __cancel(self, update: Update, _: CallbackContext) -> int:
        self.logger.info('Conversation canceled.')

        update.message.reply_text(
            'Bye! I hope we can talk again some day.',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END


if __name__ == '__main__':
    BTBManagerTelegram()