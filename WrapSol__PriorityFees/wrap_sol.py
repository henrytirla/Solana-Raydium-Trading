import asyncio
import sys
import base58
from solana.rpc.api import Client
from solana.rpc.api import Keypair
from solana.rpc.types import TokenAccountOpts
from solana.transaction import Transaction
from solders.compute_budget import set_compute_unit_price, set_compute_unit_limit
from solders.system_program import transfer, TransferParams
from solders.pubkey import Pubkey
from spl.token.instructions import create_associated_token_account, SyncNativeParams
from spl.token.constants import WRAPPED_SOL_MINT, TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import sync_native
from solana.rpc.commitment import Commitment, Confirmed
from solana.rpc.async_api import AsyncClient

from dotenv import dotenv_values
config = dotenv_values(".env")
solana_client = Client(config["RPC_HTTPS_URL"])
async_solana_client = AsyncClient(config["RPC_HTTPS_URL"])



# Initialize Solana client


private_key_string = config["PrivateKey"]
private_key_bytes = base58.b58decode(private_key_string)
payer = Keypair.from_bytes(private_key_bytes)
print(payer.pubkey())



mint_address = "So11111111111111111111111111111111111111112"

def get_specific_token_account(owner_pubkey: str, mint_pubkey: str):
        owner_pubkey_obj = Pubkey.from_string(owner_pubkey)
        mint_pubkey_obj = Pubkey.from_string(mint_pubkey)
        opts = TokenAccountOpts(mint=mint_pubkey_obj)
        response =  solana_client.get_token_accounts_by_owner(owner_pubkey_obj, opts)
        if response.value is not None and len(response.value) > 0:
            return response.value[0].pubkey  # Return the first account found
        return None

wallet_solToken_acc= get_specific_token_account(str(payer.pubkey()),mint_address)


createWSOL_Acc = create_associated_token_account(payer.pubkey(),owner=payer.pubkey(),mint=WRAPPED_SOL_MINT)

wsol_token_account= createWSOL_Acc.accounts[1].pubkey

print(f" Your WSOL token Account: {wsol_token_account}")
# Amount of SOL to wrap (in lamports, 1 SOL = 1,000,000,000 lamports)
amount_to_wrap = int(float(config['Amount_to_Wrap']) * 10**9)
params_sync = SyncNativeParams(
    program_id=TOKEN_PROGRAM_ID,
    account=wsol_token_account
)

params = TransferParams(
    from_pubkey=payer.pubkey(),
    to_pubkey=wsol_token_account,
    lamports=amount_to_wrap
)

# Create the transaction to deposit SOL into the wSOL account
transaction = Transaction()


if  wallet_solToken_acc is None:

    transaction.add(createWSOL_Acc,transfer(params),sync_native(params_sync),set_compute_unit_price(498_750),set_compute_unit_limit(4_000_000))
else:
    transaction.add(transfer(params),sync_native(params_sync),set_compute_unit_price(498_750),set_compute_unit_limit(4_000_000))




# Sign the transaction with the payer's Keypair
transaction.sign(payer)

async def send_and_confirm_transaction(client, transaction, payer, max_attempts=3):
        attempts = 0
        while attempts < max_attempts:
            try:
                txn = await async_solana_client.send_transaction(transaction, payer)
                txid_string_sig = txn.value
                if txid_string_sig:
                    print("Transaction sent")
                    print(f"Transaction Signature Waiting to be confirmed: https://solscan.io/tx/{txid_string_sig}")
                    print("Waiting Confirmation")

                confirmation_resp = await async_solana_client.confirm_transaction(
                    txid_string_sig,
                    commitment=Confirmed,
                    sleep_seconds=0.5,
                )

                if confirmation_resp.value[0].err == None and str(
                        confirmation_resp.value[0].confirmation_status) == "TransactionConfirmationStatus.Confirmed":
                    print("Transaction Confirmed")
                    print( f"Transaction Signature: https://solscan.io/tx/{txid_string_sig}")
                    return

                else:
                    print("Transaction not confirmed")
                    return False
            except asyncio.TimeoutError:
                attempts += 1
                print(f"Attempt {attempts}: Transaction not confirmed within 20 seconds. Attempting to resend.")
                print(f"Transaction signature: https://solscan.io/tx/{txid_string_sig}")
        if attempts == max_attempts:
            print("Maximum attempts reached. Transaction could not be confirmed.")


asyncio.run(send_and_confirm_transaction(solana_client, transaction, payer))