import base58
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import MemcmpOpts
import time
from solana.rpc.commitment import Confirmed
from layouts import AMM_INFO_LAYOUT_V4_1, MARKET_LAYOUT,get_offset
from solders.pubkey import Pubkey
import os
from dotenv import load_dotenv

# Load.env file
load_dotenv()

RPC_HTTPS_URL= os.getenv("RPC_HTTPS_URL")
# config = dotenv_values("Trade/.env")
# print(config)

WSOL = Pubkey.from_string("So11111111111111111111111111111111111111112")
ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string(
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
)

MINT_LEN: int = 82
"""Data length of a token mint account."""

ACCOUNT_LEN: int = 165
"""Data length of a token account."""

MULTISIG_LEN: int = 355
"""Data length of a multisig token account."""

TOKEN_PROGRAM_ID: Pubkey = Pubkey.from_string(
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
)
TOKEN_PROGRAM_ID_2022: Pubkey = Pubkey.from_string(
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
)

RAY_V4 = Pubkey.from_string("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8")
RAY_AUTHORITY_V4 = Pubkey.from_string("5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1")

OPEN_BOOK_PROGRAM = Pubkey.from_string("srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX")
# offset_base_mint = get_offset(MARKET_LAYOUT, 'base_mint')
offset_base_mint = get_offset(AMM_INFO_LAYOUT_V4_1, 'coinMintAddress')
offset_quote_mint = get_offset(AMM_INFO_LAYOUT_V4_1, 'pcMintAddress')

LAMPORTS_PER_SOL = 1000000000
# RPC_HTTPS_URL=config["RPC_HTTPS_URL"]



async def getpoolIdByMint(mint, ctx):

    start_time = time.time()
    memcmp_opts_base = MemcmpOpts(offset=offset_base_mint, bytes=bytes(mint))
    filters_tokens = [memcmp_opts_base]
    while True:
        try:
            if time.time() - start_time > 5:
                return False, False

            poolids = (await ctx.get_program_accounts(pubkey=RAY_V4, commitment=Confirmed, encoding="jsonParsed",
                                                      filters=filters_tokens)).value
            # print(poolids)
            break
        except :
            pass
    if(len(poolids) > 0):
        return poolids[0].pubkey
    else:
        return False




async def gen_pool(amm_id, ctx):


    try:
        amm_id = Pubkey.from_string(amm_id)
        ctx = AsyncClient(RPC_HTTPS_URL, commitment=Confirmed)

        start = time.time()
        while True:
            try:
                amm_data = (await ctx.get_account_info_json_parsed(amm_id)).value.data
                break
            except:
                if (time.time() - start) > 3:
                    return {"error" : "server timeout - took too long to find the pool info"}
                pass

        amm_data_decoded = AMM_INFO_LAYOUT_V4_1.parse(amm_data)
        OPEN_BOOK_PROGRAM = Pubkey.from_bytes(amm_data_decoded.serumProgramId)
        marketId = Pubkey.from_bytes(amm_data_decoded.serumMarket)
        # print("Market --- ", marketId))
        try:
            while True:
                try:
                    marketInfo = (
                        await ctx.get_account_info_json_parsed(marketId)
                    ).value.data
                    break
                except:
                    if (time.time() - start) > 3:
                        return {"error" : "server timeout - took too long to find the pool info"}
                    pass

            market_decoded = MARKET_LAYOUT.parse(marketInfo)


            pool_keys = {
                "amm_id": amm_id,
                "base_mint": Pubkey.from_bytes(market_decoded.base_mint),
                "quote_mint": Pubkey.from_bytes(market_decoded.quote_mint),
                "lp_mint": Pubkey.from_bytes(amm_data_decoded.lpMintAddress),
                "version": 4,

                "base_decimals": amm_data_decoded.coinDecimals,
                "quote_decimals": amm_data_decoded.pcDecimals,
                "lpDecimals": amm_data_decoded.coinDecimals,
                "programId": RAY_V4,
                "authority": RAY_AUTHORITY_V4,

                "open_orders": Pubkey.from_bytes(amm_data_decoded.ammOpenOrders),

                "target_orders": Pubkey.from_bytes(amm_data_decoded.ammTargetOrders),


                "base_vault": Pubkey.from_bytes(amm_data_decoded.poolCoinTokenAccount),
                "quote_vault": Pubkey.from_bytes(amm_data_decoded.poolPcTokenAccount),

                "withdrawQueue": Pubkey.from_bytes(amm_data_decoded.poolWithdrawQueue),
                "lpVault": Pubkey.from_bytes(amm_data_decoded.poolTempLpTokenAccount),

                "marketProgramId": OPEN_BOOK_PROGRAM,
                "market_id": marketId,

                "market_authority": Pubkey.create_program_address(
                    [bytes(marketId)]
                    + [bytes([market_decoded.vault_signer_nonce])]
                    + [bytes(7)],
                    OPEN_BOOK_PROGRAM,
                ),

                "market_base_vault": Pubkey.from_bytes(market_decoded.base_vault),
                "market_quote_vault": Pubkey.from_bytes(market_decoded.quote_vault),
                "bids": Pubkey.from_bytes(market_decoded.bids),
                "asks": Pubkey.from_bytes(market_decoded.asks),
                "event_queue": Pubkey.from_bytes(market_decoded.event_queue),
                "pool_open_time": amm_data_decoded.poolOpenTime
            }

            Buy_keys = [
                'amm_id', 'authority', 'base_mint', 'base_decimals', 'quote_mint', 'quote_decimals',
                'lp_mint', 'open_orders', 'target_orders', 'base_vault', 'quote_vault', 'market_id',
                'market_base_vault', 'market_quote_vault', 'market_authority', 'bids', 'asks', 'event_queue'
            ]

            transactionkeys = {key: pool_keys[key] for key in Buy_keys}

            return transactionkeys



        except:
            {"error" : "unexpected error occured"}
    except:
        return {"error" : "incorrect pair address"}

