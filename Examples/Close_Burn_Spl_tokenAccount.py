import asyncio
import os
from solana.rpc.commitment import  Finalized
from solders.compute_budget import set_compute_unit_price, set_compute_unit_limit
from solders.message import MessageV0
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from solana.transaction import Transaction
from solana.rpc import types
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import burn, BurnParams, CloseAccountParams, close_account
from dotenv import load_dotenv
load_dotenv()
payer = Keypair.from_base58_string(os.getenv('PrivateKey'))
solana_client = Client(os.getenv("RPC_HTTPS_URL"))
async_solana_client = AsyncClient(os.getenv("RPC_HTTPS_URL"))

async def get_token_accountsCount(wallet_address: Pubkey):
    owner = wallet_address
    opts = types.TokenAccountOpts(program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"))
    response = await async_solana_client.get_token_accounts_by_owner(owner, opts)
    return response.value


async def main():



      wallet_address= payer.pubkey()
      response =  await get_token_accountsCount(wallet_address)
      solana_token_accounts = {str(token_account.pubkey): token_account for token_account in response}
      tokenAccount_list= list(solana_token_accounts.keys())
      while len(tokenAccount_list)>0:
          try:
              for token in tokenAccount_list:
                  burn_instruction=[]

                  c = await async_solana_client.get_account_info_json_parsed(Pubkey.from_string(token))
                  mint_address=Pubkey.from_string(c.value.data.parsed['info']['mint'])
                  token_account=Pubkey.from_string(token)
                  balance = solana_client.get_token_account_balance(Pubkey.from_string(token))
                  amount=balance.value.amount
                  print(amount)
                  params = BurnParams(
                              amount=int(amount), account=token_account, mint=mint_address, owner=payer.pubkey(), program_id=TOKEN_PROGRAM_ID,
                          )

                  burn_inst= burn(params)
                  close_account_params = CloseAccountParams(account=token_account,
                                                            dest=payer.pubkey(),
                                                            owner=payer.pubkey(),
                                                            program_id=TOKEN_PROGRAM_ID)
                  transaction = Transaction()

                  transaction.add(close_account(close_account_params), set_compute_unit_price(25_232), set_compute_unit_limit(200_337))
                  burn_instruction.extend([burn_inst,transaction.instructions[0],transaction.instructions[1],transaction.instructions[2]])

                  block_hash = solana_client.get_latest_blockhash(commitment=Finalized)
                  print(block_hash.value.blockhash)

                  msg = MessageV0.try_compile(
                      payer=payer.pubkey(),
                      instructions=[instruction for instruction in burn_instruction],
                      address_lookup_table_accounts=[],
                      recent_blockhash=block_hash.value.blockhash,
                  )

                  tx1 = VersionedTransaction(msg, [payer])
                  txn_sig=solana_client.send_transaction(tx1)
                  print(txn_sig.value)

                  tokenAccount_list.remove(token)


          except Exception as e:
                print(e)
                continue


asyncio.run(main())