
import asyncio
import os
import time
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from dotenv import load_dotenv
from solana.rpc.api import Client
from spl.token.client import Token
from spl.token.constants import TOKEN_PROGRAM_ID
from solana.transaction import Transaction
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from jito_searcher_client import get_async_searcher_client
from jito_searcher_client.convert import versioned_tx_to_protobuf_packet
from jito_searcher_client.generated.bundle_pb2 import Bundle
from jito_searcher_client.generated.searcher_pb2 import NextScheduledLeaderRequest, SendBundleRequest
from solders.system_program import TransferParams as SoldersTransferParams
from solders.system_program import transfer as solders_transfer
import spl.token.instructions as spl_token
load_dotenv()

# Load environment variables
payer = Keypair.from_base58_string(os.getenv('PrivateKey'))

RPC_HTTPS_URL = os.getenv("RPC_HTTPS_URL")
solana_client = Client(RPC_HTTPS_URL)
async_solana_client = AsyncClient(RPC_HTTPS_URL)
LAMPORTS_PER_SOL = 1000000000

# Token-related setup
mint = Pubkey.from_string("RUpbmGF6p42AAeN1QvhFReZejQry1cLkE1PUYFVVpnL")
program_id = TOKEN_PROGRAM_ID
spl_client = Token(conn=solana_client, pubkey=mint, program_id=TOKEN_PROGRAM_ID, payer=payer)
mint_info = spl_client.get_mint_info()
decimals = mint_info.decimals


source = Pubkey.from_string('FJRDY392XSyfV9nFZC8SZij1hB3hsH121pCQi1KrvH6b') #sender
dest = Pubkey.from_string('777cz6dNUWu4hGNKda7gmnnqTz1RUxB2BGpP3S9ky466')  #receiver

# Token accounts
source_token_account = spl_client.get_accounts_by_owner(owner=source, commitment=None, encoding='base64').value[
    0].pubkey

try:
    dest_token_account = spl_client.get_accounts_by_owner(owner=dest, commitment=None, encoding='base64').value[0].pubkey
    print(dest_token_account)
    account_info = spl_client.get_account_info(dest_token_account)
    is_initialized = account_info.is_initialized


    print(f"Associated token account for the destination wallet: {dest_token_account}")

except Exception as e:
    print(e)
    print("Creating new Associative Account when sending transaction")
    dest_token_account = spl_token.get_associated_token_address(owner=dest, mint=mint)
    print(dest_token_account)
    is_initialized= False


async def send_and_confirm_transaction_via_jito(client, payer, max_attempts=3):
    attempts = 0
    while attempts <= max_attempts:
        try:
            # initialize receiving token account
            ix = spl_token.create_associated_token_account(owner=dest, mint=mint, payer=payer.pubkey())

            #sending token Instructions
            ix2 = spl_token.transfer_checked(spl_token.TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                source=source_token_account,
                mint=mint,
                dest=dest_token_account,
                owner=payer.pubkey(),
                amount=int(float(1000) * 10 ** decimals),
                decimals=8,
                signers=[payer.pubkey()]
            ))

            # # SENDING THROUGH JITO
            print("Sending Through Jito")
            #
            jito_payer = Keypair.from_base58_string(os.getenv("JITO_PAYER"))
            BLOCK_ENGINE_URL = "frankfurt.mainnet.block-engine.jito.wtf"
            jito_client = await get_async_searcher_client(BLOCK_ENGINE_URL, jito_payer)
            txs = []
            tip_account_pubkey = Pubkey.from_string(os.getenv("TIP_ACCOUNT"))
            is_leader_slot = False
            print("waiting for jito leader...")
            while not is_leader_slot:
                time.sleep(0.5)
                next_leader = await jito_client.GetNextScheduledLeader(NextScheduledLeaderRequest())
                num_slots_to_leader = next_leader.next_leader_slot - next_leader.current_slot
                print(f"waiting {num_slots_to_leader} slots to jito leader")
                is_leader_slot = num_slots_to_leader <= 5


            ix3 = solders_transfer(
                SoldersTransferParams(
                    from_pubkey=payer.pubkey(), to_pubkey=tip_account_pubkey,
                    lamports=int(0.000020002 * LAMPORTS_PER_SOL)  # TIP AMOUNT
                )
            )


            transaction=Transaction()

            if is_initialized:
                transaction.add(ix2,ix3)
            else:
                transaction.add(ix,ix2,ix3)

            instructions = [ix for ix in transaction.instructions]

            block_hash = solana_client.get_latest_blockhash(commitment=Confirmed).value.blockhash
            print(block_hash)

            msg = MessageV0.try_compile(
                payer=payer.pubkey(),
                instructions=instructions,
                address_lookup_table_accounts=[],
                recent_blockhash=block_hash,
            )

            tx1 = VersionedTransaction(msg, [payer])

            txs.append(tx1)

            packets = [versioned_tx_to_protobuf_packet(tx) for tx in txs]
            uuid_response = await jito_client.SendBundle(SendBundleRequest(bundle=Bundle(header=None, packets=packets)))

            print(f"bundle uuid: {uuid_response.uuid}")
            block_height = solana_client.get_block_height(Confirmed).value
            print(f"Block height: {block_height}")

            for tx in txs:
                confirmation_resp = await async_solana_client.confirm_transaction(
                    tx.signatures[0],
                    commitment=Confirmed,
                    sleep_seconds=0.5,
                    last_valid_block_height=block_height + 15
                )

                if confirmation_resp.value[0].err is None and str(
                        confirmation_resp.value[0].confirmation_status) == "TransactionConfirmationStatus.Confirmed":
                    print("Transaction Confirmed")
                    print(f"Transaction Signature: https://solscan.io/tx/{tx.signatures[0]}")
                    return

            attempts += 1
            print("Transaction not confirmed, retrying...")

        except Exception as e:
            print(f"Attempt {attempts}: Exception occurred - {e}")
            attempts += 1

    if attempts == max_attempts:
        print("Maximum attempts reached. Transaction could not be confirmed.")

asyncio.run(send_and_confirm_transaction_via_jito(solana_client, payer))



