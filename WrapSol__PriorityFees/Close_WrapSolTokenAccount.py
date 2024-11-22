
import asyncio
import datetime
import os
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from dotenv import load_dotenv
from solana.rpc.api import Client
from spl.token.client import Token
from spl.token.constants import TOKEN_PROGRAM_ID, WRAPPED_SOL_MINT
from solana.transaction import Transaction
from solders.compute_budget import set_compute_unit_price,set_compute_unit_limit

import spl.token.instructions as spl_token
load_dotenv()

payer = Keypair.from_base58_string(os.getenv('PrivateKey'))

RPC_HTTPS_URL = os.getenv("RPC_HTTPS_URL")
solana_client = Client(RPC_HTTPS_URL)
async_solana_client = AsyncClient(RPC_HTTPS_URL)
LAMPORTS_PER_SOL = 1000000000

wallet_solToken_acc = spl_token.get_associated_token_address(owner=payer.pubkey(), mint=WRAPPED_SOL_MINT)

spl_client = Token(solana_client, WRAPPED_SOL_MINT, TOKEN_PROGRAM_ID, payer)


class style():
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'


def getTimestamp():
    while True:
        timeStampData = datetime.datetime.now()
        currentTimeStamp = "[" + timeStampData.strftime("%H:%M:%S.%f")[:-3] + "]"
        return currentTimeStamp

async def send_and_confirm_transaction(client, payer, max_attempts=3):


    attempts = 0
    max_attempts = 3
    while attempts < max_attempts:

        try:
            token_acct_details = spl_client.get_account_info(wallet_solToken_acc)
            is_initialized = token_acct_details.is_initialized

        except Exception as e:
            print("Sol TOken Account is not initalized therefore it can't be closed")
            print(e)
            return

        try:

            transaction = Transaction()
            # Add close_account instruction to reclaim the rent-exempt reserve
            ix = spl_token.close_account(spl_token.CloseAccountParams(account=wallet_solToken_acc,
                                                  dest=payer.pubkey(),
                                                  owner=payer.pubkey(),
                                                  program_id=TOKEN_PROGRAM_ID))



            transaction.add(ix,set_compute_unit_price(498_750),set_compute_unit_limit(4_000_000))

            print("Execute Transaction...")
            txn = await async_solana_client.send_transaction(transaction, payer)
            txid_string_sig = txn.value
            if txid_string_sig:
                print("Transaction sent")
                print(getTimestamp())
                print(style.RED,f"Transaction Signature Waiting to be confirmed: https://solscan.io/tx/{txid_string_sig}"+style.RESET)
                print("Waiting Confirmation")


            block_height = solana_client.get_block_height(Confirmed).value
            print(f"Block height: {block_height}")


            confirmation_resp = await async_solana_client.confirm_transaction(
                    txid_string_sig,
                    commitment=Confirmed,
                    sleep_seconds=0.5,
                    last_valid_block_height=block_height + 15
                )

            if confirmation_resp.value[0].err == None and str(confirmation_resp.value[0].confirmation_status) == "TransactionConfirmationStatus.Confirmed":
                    print(style.GREEN + "Transaction Confirmed", style.RESET)
                    print(style.GREEN, f"Transaction Signature: https://solscan.io/tx/{txid_string_sig}", style.RESET)
                    return True

            else:
                    print("Transaction not confirmed")
                    attempts += 1
                    print("Transaction not confirmed, retrying...")







        except Exception as e:
            print(f"Attempt {attempts}: Exception occurred - {e}")
            attempts += 1
    if attempts == max_attempts:
       print("Maximum attempts reached. Transaction could not be confirmed.")


asyncio.run(send_and_confirm_transaction(solana_client, payer))
