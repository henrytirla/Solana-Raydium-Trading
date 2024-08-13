
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
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID, WRAPPED_SOL_MINT
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
tip_account_pubkey = Pubkey.from_string(os.getenv("TIP_ACCOUNT"))

wallet_solToken_acc = spl_token.get_associated_token_address(owner=payer.pubkey(), mint=WRAPPED_SOL_MINT)

spl_client = Token(solana_client, WRAPPED_SOL_MINT, TOKEN_PROGRAM_ID, payer)


async def send_and_confirm_transaction_via_jito(client, payer, max_attempts=3):


    attempts = 0
    max_attempts = 3
    while attempts < max_attempts:

        try:
            token_acct_details = spl_client.get_account_info(wallet_solToken_acc)
            is_initialized = token_acct_details.is_initialized

        except Exception as e:
            print("Sol TOken Account is not initalized therefor it can't be closed")
            print(e)
            return

        try:

            transaction = Transaction()
            # Add close_account instruction to reclaim the rent-exempt reserve
            ix = spl_token.close_account(spl_token.CloseAccountParams(account=wallet_solToken_acc,
                                                  dest=payer.pubkey(),
                                                  owner=payer.pubkey(),
                                                  program_id=TOKEN_PROGRAM_ID))
            ix2 = solders_transfer(
                SoldersTransferParams(
                    from_pubkey=payer.pubkey(), to_pubkey=tip_account_pubkey,
                    lamports=int(0.000020002 * LAMPORTS_PER_SOL)  # TIP AMOUNT
                )
            )
            print("Sending Through Jito")
            #
            jito_payer = Keypair.from_base58_string(os.getenv("JITO_PAYER"))
            BLOCK_ENGINE_URL = "frankfurt.mainnet.block-engine.jito.wtf"
            jito_client = await get_async_searcher_client(BLOCK_ENGINE_URL, jito_payer)
            txs = []
            is_leader_slot = False
            print("waiting for jito leader...")
            while not is_leader_slot:
                time.sleep(0.5)
                next_leader = await jito_client.GetNextScheduledLeader(NextScheduledLeaderRequest())
                num_slots_to_leader = next_leader.next_leader_slot - next_leader.current_slot
                print(f"waiting {num_slots_to_leader} slots to jito leader")
                is_leader_slot = num_slots_to_leader <= 5


            transaction.add(ix, ix2)

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
