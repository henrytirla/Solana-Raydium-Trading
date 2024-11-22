from io import BytesIO

import requests
from borsh_construct import CStruct, String, U8, U16, U64, Vec, Option, Bool, Enum

from construct import Bytes, Int8ul, Int64ul, Padding, BitsInteger, BitsSwapped, BitStruct, Const, Flag, BytesInteger
from construct import Struct as cStruct

import base58, json


from spl.token.instructions import create_associated_token_account, get_associated_token_address

from solders.pubkey import Pubkey
from solders.instruction import Instruction

from solana.rpc.types import TokenAccountOpts
from solana.transaction import AccountMeta


class MyEncoder(json.JSONEncoder):
    def default(self, o):
        if type(o) is bytes:
            return o.decode("utf-8")
        return super(MyEncoder, self).default(o)


def remove_bytesio(obj):
    if isinstance(obj, dict):
        return {
            k: remove_bytesio(v) for k, v in obj.items() if not isinstance(v, BytesIO)
        }
    elif isinstance(obj, list):
        return [remove_bytesio(v) for v in obj if not isinstance(v, BytesIO)]
    else:
        return obj

def get_offset(struct, field):
    offset = 0
    for item in struct.subcons:
        if item.name == field:
            return offset
        else:
            offset += item.sizeof()
    return None
def convert_bytes_to_pubkey(obj):
    if isinstance(obj, dict):
        return {k: convert_bytes_to_pubkey(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_bytes_to_pubkey(v) for v in obj]
    elif isinstance(obj, bytes):
        return str(Pubkey.from_bytes(obj))
    else:
        return obj


def getMetaData(data):
    decoded_info = base58.b58decode(data)
    # structure of the instruction
    instruction_structure = CStruct(
        "instructionDiscriminator" / U8,
        "createMetadataAccountArgsV3"
        / CStruct(
            "data"
            / CStruct(
                "name" / String,
                "symbol" / String,
                "uri" / String,
                "sellerFeeBasisPoints" / U16,
                "creators"
                / Option(
                    Vec(CStruct("address" / Bytes(32), "verified" / Bool, "share" / U8))
                ),
                "collection" / Option(CStruct("verified" / Bool, "key" / Bytes(32))),
                "uses"
                / Option(
                    CStruct(
                        "useMethod"
                        / Enum("Burn", "Multiple", "Single", enum_name="UseMethod"),
                        "remaining" / U64,
                        "total" / U64,
                    )
                ),
            ),
            "isMutable" / Bool,
            "collectionDetails"
            / Option(String),  # fixme: string is not correct, insert correct type
        ),
    )
    metadata = instruction_structure.parse(decoded_info)
    metadata = remove_bytesio(metadata)
    metadata = convert_bytes_to_pubkey(metadata)

    return json.dumps(metadata)


SWAP_LAYOUT = cStruct(
    "instruction" / Int8ul, "amount_in" / Int64ul, "min_amount_out" / Int64ul
)



AMM_INFO_LAYOUT_V4_1 = cStruct(
    "status" / Int64ul,
    "nonce" / Int64ul,
    "orderNum" / Int64ul,
    "depth" / Int64ul,
    "coinDecimals" / Int64ul,
    "pcDecimals" / Int64ul,
    "state" / Int64ul,
    "resetFlag" / Int64ul,
    "minSize" / Int64ul,
    "volMaxCutRatio" / Int64ul,
    "amountWaveRatio" / Int64ul,
    "coinLotSize" / Int64ul,
    "pcLotSize" / Int64ul,
    "minPriceMultiplier" / Int64ul,
    "maxPriceMultiplier" / Int64ul,
    "systemDecimalsValue" / Int64ul,
    #   // Fees
    "minSeparateNumerator" / Int64ul,
    "minSeparateDenominator" / Int64ul,
    "tradeFeeNumerator" / Int64ul,
    "tradeFeeDenominator" / Int64ul,
    "pnlNumerator" / Int64ul,
    "pnlDenominator" / Int64ul,
    "swapFeeNumerator" / Int64ul,
    "swapFeeDenominator" / Int64ul,
    #   // OutPutData
    "needTakePnlCoin" / Int64ul,
    "needTakePnlPc" / Int64ul,
    "totalPnlPc" / Int64ul,
    "totalPnlCoin" / Int64ul,
    "poolOpenTime" / Int64ul,
    "punishPcAmount" / Int64ul,
    "punishCoinAmount" / Int64ul,
    "orderbookToInitTime" / Int64ul,
    "swapCoinInAmount" / BytesInteger(16, signed=False, swapped=True),
    "swapPcOutAmount" / BytesInteger(16, signed=False, swapped=True),
    "swapCoin2PcFee" / Int64ul,
    "swapPcInAmount" / BytesInteger(16, signed=False, swapped=True),
    "swapCoinOutAmount" / BytesInteger(16, signed=False, swapped=True),
    "swapPc2CoinFee" / Int64ul,
    "poolCoinTokenAccount" / Bytes(32),
    "poolPcTokenAccount" / Bytes(32),
    "coinMintAddress" / Bytes(32),
    "pcMintAddress" / Bytes(32),
    "lpMintAddress" / Bytes(32),
    "ammOpenOrders" / Bytes(32),
    "serumMarket" / Bytes(32),
    "serumProgramId" / Bytes(32),
    "ammTargetOrders" / Bytes(32),
    "poolWithdrawQueue" / Bytes(32),
    "poolTempLpTokenAccount" / Bytes(32),
    "ammOwner" / Bytes(32),
    "pnlOwner" / Bytes(32),
)


ACCOUNT_FLAGS_LAYOUT = BitsSwapped(
    BitStruct(
        "initialized" / Flag,
        "market" / Flag,
        "open_orders" / Flag,
        "request_queue" / Flag,
        "event_queue" / Flag,
        "bids" / Flag,
        "asks" / Flag,
        Const(0, BitsInteger(57)),  # Padding
    )
)

MARKET_LAYOUT = cStruct(
    Padding(5),
    "account_flags" / ACCOUNT_FLAGS_LAYOUT,
    "own_address" / Bytes(32),
    "vault_signer_nonce" / Int64ul,
    "base_mint" / Bytes(32),
    "quote_mint" / Bytes(32),
    "base_vault" / Bytes(32),
    "base_deposits_total" / Int64ul,
    "base_fees_accrued" / Int64ul,
    "quote_vault" / Bytes(32),
    "quote_deposits_total" / Int64ul,
    "quote_fees_accrued" / Int64ul,
    "quote_dust_threshold" / Int64ul,
    "request_queue" / Bytes(32),
    "event_queue" / Bytes(32),
    "bids" / Bytes(32),
    "asks" / Bytes(32),
    "base_lot_size" / Int64ul,
    "quote_lot_size" / Int64ul,
    "fee_rate_bps" / Int64ul,
    "referrer_rebate_accrued" / Int64ul,
    Padding(7),
)

MINT_LAYOUT = cStruct(Padding(44), "decimals" / Int8ul, Padding(37))


POOL_INFO_LAYOUT = cStruct("instruction" / Int8ul, "simulate_type" / Int8ul)

LIQ_LAYOUT = cStruct("instruction" / Int8ul, "amount_in" / Int64ul)


###BUYING

AMM_PROGRAM_ID = Pubkey.from_string('675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8')
SERUM_PROGRAM_ID = Pubkey.from_string('srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX')
def get_token_account(ctx,
                      owner: Pubkey.from_string,
                      mint: Pubkey.from_string):
    try:
        account_data = ctx.get_token_accounts_by_owner(owner, TokenAccountOpts(mint))
        return account_data.value[0].pubkey, None
    except:
        swap_associated_token_address = get_associated_token_address(owner, mint)
        swap_token_account_Instructions = create_associated_token_account(owner, owner, mint)
        return swap_associated_token_address, swap_token_account_Instructions


def make_swap_instruction(amount_in: int, token_account_in: Pubkey.from_string, token_account_out: Pubkey.from_string,
                          accounts: dict, mint, ctx, owner) -> Instruction:
    tokenPk = mint
    accountProgramId = ctx.get_account_info_json_parsed(tokenPk)
    TOKEN_PROGRAM_ID = accountProgramId.value.owner

    keys = [
        AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["amm_id"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["authority"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["open_orders"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["target_orders"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["base_vault"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["quote_vault"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=SERUM_PROGRAM_ID, is_signer=False, is_writable=False),
        AccountMeta(pubkey=accounts["market_id"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["bids"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["asks"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["event_queue"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["market_base_vault"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["market_quote_vault"], is_signer=False, is_writable=True),
        AccountMeta(pubkey=accounts["market_authority"], is_signer=False, is_writable=False),
        AccountMeta(pubkey=token_account_in, is_signer=False, is_writable=True),  # UserSourceTokenAccount
        AccountMeta(pubkey=token_account_out, is_signer=False, is_writable=True),  # UserDestTokenAccount
        AccountMeta(pubkey=owner.pubkey(), is_signer=True, is_writable=False)  # UserOwner
    ]

    data = SWAP_LAYOUT.build(
        dict(
            instruction=9,
            amount_in=int(amount_in),
            min_amount_out=0
        )
    )
    return Instruction(AMM_PROGRAM_ID, data, keys)

def getSymbol(token):
    # usdc and usdt
    exclude = ['EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB']

    if token not in exclude:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token}"

        Token_Symbol = ""
        Sol_symbol = ""
        try:
            response = requests.get(url)

            # Check if the request was successful (status code 200)
            if response.status_code == 200:
                resp = response.json()
                print("Response:", resp['pairs'][0]['baseToken']['symbol'])
                for pair in resp['pairs']:
                    quoteToken = pair['quoteToken']['symbol']

                    if quoteToken == 'SOL':
                        Token_Symbol = pair['baseToken']['symbol']
                        Sol_symbol = quoteToken
                        return Token_Symbol, Sol_symbol


            else:
                print(f"[getSymbol] Request failed with status code {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"[getSymbol] error occurred: {e}")
        except:
            a = 1

        return Token_Symbol, Sol_symbol
    else:
        if token == 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v':
            return "USDC", "SOL"
        elif token == 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v':
            return "USDT", "SOL"

from borsh_construct import CStruct, U64, Bytes
from construct import Bytes, Int8ul, Int32ul, Int64ul, Pass, Switch

PUBLIC_KEY_LAYOUT = Bytes(32)
market_state_layout_v3 = CStruct(
    "blob1" / Bytes(5),
    "blob2" / Bytes(8),
    "ownAddress" / PUBLIC_KEY_LAYOUT,
    "vaultSignerNonce" / U64,
    "baseMint" / PUBLIC_KEY_LAYOUT,
    "quoteMint" / PUBLIC_KEY_LAYOUT,
    "baseVault" / PUBLIC_KEY_LAYOUT,
    "baseDepositsTotal" / U64,
    "baseFeesAccrued" / U64,
    "quoteVault" / PUBLIC_KEY_LAYOUT,
    "quoteDepositsTotal" / U64,
    "quoteFeesAccrued" / U64,
    "quoteDustThreshold" / U64,
    "requestQueue" / PUBLIC_KEY_LAYOUT,
    "eventQueue" / PUBLIC_KEY_LAYOUT,
    "bids" / PUBLIC_KEY_LAYOUT,
    "asks" / PUBLIC_KEY_LAYOUT,
    "baseLotSize" / U64,
    "quoteLotSize" / U64,
    "feeRateBps" / U64,
    "referrerRebatesAccrued" / U64,
    "blob3" / Bytes(7)
)
SPL_ACCOUNT_LAYOUT = CStruct(
    "mint" / PUBLIC_KEY_LAYOUT,
    "owner" / PUBLIC_KEY_LAYOUT,
    "amount" / U64,
    "delegateOption" / Int32ul,
    "delegate" / PUBLIC_KEY_LAYOUT,
    "state" / Int8ul,
    "isNativeOption" / Int32ul,
    "isNative" / U64,
    "delegatedAmount" / U64,
    "closeAuthorityOption" / Int32ul,
    "closeAuthority" / PUBLIC_KEY_LAYOUT
)


SPL_MINT_LAYOUT = CStruct(
  "mintAuthorityOption"/ Int32ul,
  'mintAuthority'/PUBLIC_KEY_LAYOUT,
  'supply'/U64,
  'decimals'/Int8ul,
  'isInitialized'/Int8ul,
  'freezeAuthorityOption'/Int32ul,
  'freezeAuthority'/PUBLIC_KEY_LAYOUT
)