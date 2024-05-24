import asyncio
import datetime
import time
from solana.rpc.types import TokenAccountOpts
from solders.pubkey import Pubkey
from solders.signature import Signature
from solana.rpc.commitment import Commitment, Confirmed
from solana.rpc.api import RPCException
from solana.rpc.api import Client, Keypair
from solana.rpc.async_api import AsyncClient
from solders.compute_budget import set_compute_unit_price,set_compute_unit_limit
from solders.transaction import Transaction
from utils.create_close_account import  fetch_pool_keys, get_token_account, make_swap_instruction
from utils.birdeye import getSymbol
from solana.transaction import Transaction
from spl.token.constants import WRAPPED_SOL_MINT
from solana.rpc.async_api import AsyncClient
from utils.pool_information import gen_pool, getpoolIdByMint
import os
from dotenv import load_dotenv

# Load.env file
load_dotenv()

# config = dotenv_values(".env")

RPC_HTTPS_URL= os.getenv("RPC_HTTPS_URL")
solana_client = Client(os.getenv("RPC_HTTPS_URL"))
async_solana_client = AsyncClient(os.getenv("RPC_HTTPS_URL"))
payer=Keypair.from_base58_string(os.getenv("PrivateKey"))
Wsol_TokenAccount=os.getenv('WSOL_TokenAccount')


AMM_PROGRAM_ID = Pubkey.from_string('675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8')
SERUM_PROGRAM_ID = Pubkey.from_string('srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX')
LAMPORTS_PER_SOL = 1000000000
MAX_RETRIES = 2
RETRY_DELAY = 3

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

async def get_specific_token_account(owner_pubkey: str, mint_pubkey: str):
    async with AsyncClient(RPC_HTTPS_URL) as client:
        owner_pubkey_obj = Pubkey.from_string(owner_pubkey)
        mint_pubkey_obj = Pubkey.from_string(mint_pubkey)
        # Using get_token_accounts_by_owner to fetch token accounts
        opts = TokenAccountOpts(mint=mint_pubkey_obj)
        response = await client.get_token_accounts_by_owner(owner_pubkey_obj, opts)
        if len(response.value) ==1 :
            return response.value[0].pubkey  # Return the first account found
    return None




async def buy(solana_client, TOKEN_TO_SWAP_BUY, payer, amount):


    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            # Re-init transaction preparation
            token_symbol, SOl_Symbol = getSymbol(TOKEN_TO_SWAP_BUY)
            mint = Pubkey.from_string(TOKEN_TO_SWAP_BUY)
            # mint= TOKEN_TO_SWAP_BUY

            try:

                tokenPool_ID = await getpoolIdByMint(mint, AsyncClient(RPC_HTTPS_URL, commitment=Confirmed))

                if tokenPool_ID is not False:

                    fetch_pool_key = await gen_pool(str(tokenPool_ID), AsyncClient(RPC_HTTPS_URL, commitment=Confirmed))
                    pool_keys = fetch_pool_key
                else:
                    print("AMMID NOT FOUND SEARCHING WILL BE FETCHING WITH RAYDIUM SDK")
                    return

                    # pool_keys = fetch_pool_keys(str(mint))
            except Exception as e:
                print(e)
            amount_in = int(amount * LAMPORTS_PER_SOL)

            swap_associated_token_address, swap_token_account_Instructions = get_token_account(solana_client, payer.pubkey(), mint)
            swap_tx = Transaction()
            WSOL_token_account = Pubkey.from_string(Wsol_TokenAccount)
            instructions_swap = make_swap_instruction(amount_in, WSOL_token_account, swap_associated_token_address, pool_keys, mint, solana_client, payer)
            if swap_token_account_Instructions != None:

                swap_tx.add(swap_token_account_Instructions)


            swap_tx.add(instructions_swap,set_compute_unit_price(25_232),set_compute_unit_limit(200_337))


            # Execute Transaction
            print("Execute Transaction...")
            txn = await async_solana_client.send_transaction(swap_tx, payer)
            txid_string_sig = txn.value
            print(txid_string_sig)
            if txid_string_sig:
                print("Transaction sent")
                print(style.RED,f"Transaction Signature Waiting to be confirmed: https://solscan.io/tx/{txid_string_sig}"+style.RESET)
                print("Waiting Confirmation")

            block_height = solana_client.get_block_height(Confirmed).value
            print(f"Block height: {block_height}")


            confirmation_resp = await async_solana_client.confirm_transaction(
                txid_string_sig,
                commitment=Confirmed,
                sleep_seconds=0.5,
                last_valid_block_height=block_height + 50


            )


            if  confirmation_resp.value[0].err== None and str(confirmation_resp.value[0].confirmation_status) =="TransactionConfirmationStatus.Confirmed":
                print(style.GREEN+"Transaction Confirmed",style.RESET)
                print(style.GREEN,f"Transaction Signature: https://solscan.io/tx/{txid_string_sig}",style.RESET)

                return True

            else:
                print("Transaction not confirmed")
                return False

        except asyncio.TimeoutError:
            print("Transaction confirmation timed out. Retrying...")
            retry_count += 1
            time.sleep(RETRY_DELAY)
        except RPCException as e:
            print(f"RPC Error: [{e.args[0].message}]... Retrying...")
            retry_count += 1
            time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"Unhandled exception: {e}. Retrying...")
            retry_count += 1
            time.sleep(RETRY_DELAY)

    print("Failed to confirm transaction after maximum retries.")
    return False

async def main():

    token_toBuy="RUpbmGF6p42AAeN1QvhFReZejQry1cLkE1PUYFVVpnL"
    print(payer.pubkey())
    await buy(solana_client, token_toBuy, payer, 0.012593837)

asyncio.run(main())