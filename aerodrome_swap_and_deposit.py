# aerodrome_auto_deposit.py
import time
import math
from decimal import Decimal, getcontext
from wallet_setup import web3, wallet_address, private_key, weth_contract, usdc_contract

# Import rebalance function from aerodrome_swap
from aerodrome_swap import rebalance_wallet, get_wallet_balances

getcontext().prec = 28

# Contract addresses
NPM_ADDRESS = web3.to_checksum_address("0x827922686190790b37229fd06084350e74485b72")
POOL_ADDRESS = web3.to_checksum_address("0xb2cc224c1c9feE385f8ad6a55b4d94E92359DC59")
HELPER_ADDRESS = web3.to_checksum_address("0x9c62ab10577fB3C20A22E231b7703Ed6D456CC7a")
WETH_ADDRESS = web3.to_checksum_address("0x4200000000000000000000000000000000000006")
USDC_ADDRESS = web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")

# ABIs
POOL_ABI = '''
[{"inputs":[],"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"bool","name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"},
{"inputs":[],"name":"tickSpacing","outputs":[{"internalType":"int24","name":"","type":"int24"}],"stateMutability":"view","type":"function"}]
'''

HELPER_ABI = '''
[
    {"inputs":[{"internalType":"uint160","name":"sqrtRatioX96","type":"uint160"},{"internalType":"uint160","name":"sqrtRatioAX96","type":"uint160"},{"internalType":"uint160","name":"sqrtRatioBX96","type":"uint160"},{"internalType":"uint128","name":"liquidity","type":"uint128"}],"name":"getAmountsForLiquidity","outputs":[{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"pure","type":"function"},
    {"inputs":[{"internalType":"int24","name":"tick","type":"int24"}],"name":"getSqrtRatioAtTick","outputs":[{"internalType":"uint160","name":"sqrtRatioX96","type":"uint160"}],"stateMutability":"pure","type":"function"}
]
'''

# Full ERC20 ABI with allowance and approve
ERC20_ABI = '''
[{"constant":true,"inputs":[{"name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},
{"constant":false,"inputs":[{"name":"spender","type":"address"},{"name":"value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},
{"constant":true,"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]
'''

# Full NPM ABI
NPM_ABI = '''
[{"inputs":[{"internalType":"address","name":"_factory","type":"address"},{"internalType":"address","name":"_WETH9","type":"address"},{"internalType":"address","name":"_tokenDescriptor","type":"address"},{"internalType":"string","name":"name","type":"string"},{"internalType":"string","name":"symbol","type":"string"}],"stateMutability":"nonpayable","type":"constructor"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"owner","type":"address"},{"indexed":true,"internalType":"address","name":"approved","type":"address"},{"indexed":true,"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"Approval","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"owner","type":"address"},{"indexed":true,"internalType":"address","name":"operator","type":"address"},{"indexed":false,"internalType":"bool","name":"approved","type":"bool"}],"name":"ApprovalForAll","type":"event"},{"anonymous":false,"inputs":[{"indexed":false,"internalType":"uint256","name":"_fromTokenId","type":"uint256"},{"indexed":false,"internalType":"uint256","name":"_toTokenId","type":"uint256"}],"name":"BatchMetadataUpdate","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"uint256","name":"tokenId","type":"uint256"},{"indexed":false,"internalType":"address","name":"recipient","type":"address"},{"indexed":false,"internalType":"uint256","name":"amount0","type":"uint256"},{"indexed":false,"internalType":"uint256","name":"amount1","type":"uint256"}],"name":"Collect","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"uint256","name":"tokenId","type":"uint256"},{"indexed":false,"internalType":"uint128","name":"liquidity","type":"uint128"},{"indexed":false,"internalType":"uint256","name":"amount0","type":"uint256"},{"indexed":false,"internalType":"uint256","name":"amount1","type":"uint256"}],"name":"DecreaseLiquidity","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"uint256","name":"tokenId","type":"uint256"},{"indexed":false,"internalType":"uint128","name":"liquidity","type":"uint128"},{"indexed":false,"internalType":"uint256","name":"amount0","type":"uint256"},{"indexed":false,"internalType":"uint256","name":"amount1","type":"uint256"}],"name":"IncreaseLiquidity","type":"event"},{"anonymous":false,"inputs":[{"indexed":false,"internalType":"uint256","name":"_tokenId","type":"uint256"}],"name":"MetadataUpdate","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"tokenDescriptor","type":"address"}],"name":"TokenDescriptorChanged","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"from","type":"address"},{"indexed":true,"internalType":"address","name":"to","type":"address"},{"indexed":true,"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"Transfer","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"owner","type":"address"}],"name":"TransferOwnership","type":"event"},{"inputs":[],"name":"DOMAIN_SEPARATOR","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"PERMIT_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"WETH9","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"approve","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"baseURI","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"pure","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"burn","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"components":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint128","name":"amount0Max","type":"uint128"},{"internalType":"uint128","name":"amount1Max","type":"uint128"}],"internalType":"struct INonfungiblePositionManager.CollectParams","name":"params","type":"tuple"}],"name":"collect","outputs":[{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"},{"inputs":[{"components":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"amount0Min","type":"uint256"},{"internalType":"uint256","name":"amount1Min","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"internalType":"struct INonfungiblePositionManager.DecreaseLiquidityParams","name":"params","type":"tuple"}],"name":"decreaseLiquidity","outputs":[{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"},{"inputs":[],"name":"factory","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"getApproved","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"components":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"uint256","name":"amount0Desired","type":"uint256"},{"internalType":"uint256","name":"amount1Desired","type":"uint256"},{"internalType":"uint256","name":"amount0Min","type":"uint256"},{"internalType":"uint256","name":"amount1Min","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"internalType":"struct INonfungiblePositionManager.IncreaseLiquidityParams","name":"params","type":"tuple"}],"name":"increaseLiquidity","outputs":[{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"operator","type":"address"}],"name":"isApprovedForAll","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[{"components":[{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"int24","name":"tickSpacing","type":"int24"},{"internalType":"int24","name":"tickLower","type":"int24"},{"internalType":"int24","name":"tickUpper","type":"int24"},{"internalType":"uint256","name":"amount0Desired","type":"uint256"},{"internalType":"uint256","name":"amount1Desired","type":"uint256"},{"internalType":"uint256","name":"amount0Min","type":"uint256"},{"internalType":"uint256","name":"amount1Min","type":"uint256"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"}],"internalType":"struct INonfungiblePositionManager.MintParams","name":"params","type":"tuple"}],"name":"mint","outputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"bytes[]","name":"data","type":"bytes[]"}],"name":"multicall","outputs":[{"internalType":"bytes[]","name":"results","type":"bytes[]"}],"stateMutability":"payable","type":"function"},{"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"ownerOf","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"permit","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"internalType":"uint96","name":"nonce","type":"uint96"},{"internalType":"address","name":"operator","type":"address"},{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"int24","name":"tickSpacing","type":"int24"},{"internalType":"int24","name":"tickLower","type":"int24"},{"internalType":"int24","name":"tickUpper","type":"int24"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"feeGrowthInside0LastX128","type":"uint256"},{"internalType":"uint256","name":"feeGrowthInside1LastX128","type":"uint256"},{"internalType":"uint128","name":"tokensOwed0","type":"uint128"},{"internalType":"uint128","name":"tokensOwed1","type":"uint128"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"refundETH","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"safeTransferFrom","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"bytes","name":"_data","type":"bytes"}],"name":"safeTransferFrom","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"selfPermit","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"nonce","type":"uint256"},{"internalType":"uint256","name":"expiry","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"selfPermitAllowed","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"nonce","type":"uint256"},{"internalType":"uint256","name":"expiry","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"selfPermitAllowedIfNecessary","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"selfPermitIfNecessary","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"operator","type":"address"},{"internalType":"bool","name":"approved","type":"bool"}],"name":"setApprovalForAll","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"_owner","type":"address"}],"name":"setOwner","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"_tokenDescriptor","type":"address"}],"name":"setTokenDescriptor","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"bytes4","name":"interfaceId","type":"bytes4"}],"name":"supportsInterface","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"amountMinimum","type":"uint256"},{"internalType":"address","name":"recipient","type":"address"}],"name":"sweepToken","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"tokenDescriptor","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"tokenURI","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"transferFrom","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"amount0Owed","type":"uint256"},{"internalType":"uint256","name":"amount1Owed","type":"uint256"},{"internalType":"bytes","name":"data","type":"bytes"}],"name":"uniswapV3MintCallback","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"amountMinimum","type":"uint256"},{"internalType":"address","name":"recipient","type":"address"}],"name":"unwrapWETH9","outputs":[],"stateMutability":"payable","type":"function"},{"stateMutability":"payable","type":"receive"}]
'''

# Initialize contracts
pool_contract = web3.eth.contract(address=POOL_ADDRESS, abi=POOL_ABI)
helper_contract = web3.eth.contract(address=HELPER_ADDRESS, abi=HELPER_ABI)
weth_token = web3.eth.contract(address=WETH_ADDRESS, abi=ERC20_ABI)
usdc_token = web3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)
npm_contract = web3.eth.contract(address=NPM_ADDRESS, abi=NPM_ABI)

def get_pool_info():
    """Get current tick and tick spacing from the pool"""
    slot0 = pool_contract.functions.slot0().call()
    current_tick = slot0[1]
    sqrt_price_x96 = slot0[0]
    tick_spacing = pool_contract.functions.tickSpacing().call()

    # Calculate price from sqrtPriceX96 using the correct formula
    # This calculates USDC price per WETH directly
    price = (Decimal(sqrt_price_x96) / Decimal(2**96)) ** 2 * Decimal(1e12)
    eth_price_in_usdc = float(price)

    print(f"Current tick: {current_tick}")
    print(f"Tick spacing: {tick_spacing}")
    print(f"Current ETH price: ${eth_price_in_usdc:.2f}")

    return current_tick, tick_spacing, sqrt_price_x96, eth_price_in_usdc

def calculate_two_percent_tick_range(current_tick, tick_spacing):
    """Calculate a symmetrical +/-2% price range around the current price"""
    # Calculate how many ticks correspond to a 2% price change
    ticks_for_2_percent = int(math.log(1.02) / math.log(1.0001))

    # Calculate the raw target ticks
    lower_tick_target = current_tick - ticks_for_2_percent
    upper_tick_target = current_tick + ticks_for_2_percent

    # Calculate the midpoint (should be very close to current_tick)
    midpoint = (lower_tick_target + upper_tick_target) / 2

    # Round the midpoint to the nearest tick spacing
    midpoint_rounded = round(midpoint / tick_spacing) * tick_spacing

    # Calculate equal distance from the rounded midpoint
    half_range = ((upper_tick_target - lower_tick_target) / 2)
    # Round to the nearest multiple of tick spacing, but never less than 1 spacing
    half_range_ticks = max(1, round(half_range / tick_spacing)) * tick_spacing

    # Calculate new lower and upper ticks
    lower_tick = midpoint_rounded - half_range_ticks
    upper_tick = midpoint_rounded + half_range_ticks

    # Verify the calculated ticks by determining the price percentage change
    def calculate_price_from_tick(tick):
        sqrt_price_x96 = helper_contract.functions.getSqrtRatioAtTick(tick).call()
        price = (Decimal(sqrt_price_x96) / Decimal(2**96)) ** 2 * Decimal(1e12)
        return price

    # Get the current price
    current_price = calculate_price_from_tick(current_tick)

    # Get the price at the lower and upper ticks
    lower_price = calculate_price_from_tick(lower_tick)
    upper_price = calculate_price_from_tick(upper_tick)

    # Calculate the percentage difference
    lower_pct_diff = ((lower_price / current_price) - 1) * 100
    upper_pct_diff = ((upper_price / current_price) - 1) * 100

    print(f"\n+/-2% Price Range Details:")
    print(f"Target range: {ticks_for_2_percent} ticks from current (~2%)")
    print(f"Current ETH price: ${float(current_price):.2f}")
    print(f"Lower tick: {lower_tick}")
    print(f"Upper tick: {upper_tick}")
    print(f"Lower ETH price: ${float(lower_price):.2f} ({float(lower_pct_diff):.2f}%)")
    print(f"Upper ETH price: ${float(upper_price):.2f} ({float(upper_pct_diff):.2f}%)")

    return lower_tick, upper_tick

def calculate_optimal_amounts(weth_amount, lower_tick, upper_tick, current_tick, sqrt_price_x96):
    """Calculate optimal token amounts for providing liquidity using exact WETH amount"""
    # Convert WETH amount to wei
    weth_amount_wei = int(Decimal(weth_amount) * Decimal(1e18))

    # Get sqrt price at ticks
    sqrt_lower_x96 = helper_contract.functions.getSqrtRatioAtTick(lower_tick).call()
    sqrt_upper_x96 = helper_contract.functions.getSqrtRatioAtTick(upper_tick).call()

    # Check position relative to current price
    if current_tick < lower_tick:
        # Position entirely above current price - only USDC needed
        print("Position is above current price - only using USDC")

        # Calculate the price range factor
        lower_price = (Decimal(sqrt_lower_x96) / Decimal(2**96)) ** 2
        upper_price = (Decimal(sqrt_upper_x96) / Decimal(2**96)) ** 2

        # Get current price
        current_price = (Decimal(sqrt_price_x96) / Decimal(2**96)) ** 2

        # Calculate ETH price in USDC using logarithms to avoid precision issues
        log10_weth_usdc_price = current_tick * Decimal(math.log10(1.0001))
        log10_eth_price = -log10_weth_usdc_price + 12
        eth_price_in_usdc = Decimal(10) ** log10_eth_price

        # Calculate USDC amount needed
        usdc_amount = int(Decimal(weth_amount) * eth_price_in_usdc * Decimal(1e6))
        return 0, usdc_amount

    elif current_tick > upper_tick:
        # Position entirely below current price - only WETH needed
        print("Position is below current price - only using WETH")
        return weth_amount_wei, 0

    else:
        # Position straddles current price - we need to calculate liquidity
        # First, calculate liquidity based on WETH amount
        # L = weth_amount_wei / (sqrt(upper) - sqrt(current)) if current_tick >= lower_tick

        # Calculate delta sqrt prices
        sqrt_current = Decimal(sqrt_price_x96) / Decimal(2**96)
        sqrt_lower = Decimal(sqrt_lower_x96) / Decimal(2**96)
        sqrt_upper = Decimal(sqrt_upper_x96) / Decimal(2**96)

        # Calculate liquidity
        # For positions that cross the current price:
        # L = WETH / (1/sqrt(Pl) - 1/sqrt(Pc)) for WETH
        # L = USDC / (sqrt(Pc) - sqrt(Pl)) for USDC
        # Where Pl = lower price, Pc = current price, Pu = upper price

        # Calculate liquidity from WETH
        if sqrt_current <= sqrt_upper:
            # The formula is different depending on whether current price is below upper price
            delta = (Decimal(1) / sqrt_lower) - (Decimal(1) / sqrt_current)
            if delta > 0:  # Avoid division by zero
                liquidity = Decimal(weth_amount_wei) / delta
            else:
                liquidity = 0
        else:
            # Current price is above upper tick, all WETH
            delta = (Decimal(1) / sqrt_lower) - (Decimal(1) / sqrt_upper)
            if delta > 0:  # Avoid division by zero
                liquidity = Decimal(weth_amount_wei) / delta
            else:
                liquidity = 0

        # Convert to a reasonable liquidity value
        liquidity_value = int(liquidity)

        # Use getAmountsForLiquidity to get the exact token amounts
        amounts = helper_contract.functions.getAmountsForLiquidity(
            sqrt_price_x96,
            sqrt_lower_x96,
            sqrt_upper_x96,
            liquidity_value
        ).call()

        # Get WETH and USDC amounts
        calculated_weth = amounts[0]
        calculated_usdc = amounts[1]

        # If the calculated WETH is different than our input WETH,
        # we need to scale the liquidity and recalculate
        if calculated_weth != weth_amount_wei and calculated_weth > 0:
            scaling_factor = Decimal(weth_amount_wei) / Decimal(calculated_weth)
            liquidity_value = int(Decimal(liquidity_value) * scaling_factor)

            # Recalculate with the new liquidity
            amounts = helper_contract.functions.getAmountsForLiquidity(
                sqrt_price_x96,
                sqrt_lower_x96,
                sqrt_upper_x96,
                liquidity_value
            ).call()

            calculated_weth = amounts[0]
            calculated_usdc = amounts[1]

        # Return the calculated amounts
        return calculated_weth, calculated_usdc

def ensure_approval(token, amount):
    """Ensure token is approved for position manager"""
    token_symbol = "WETH" if token.address == WETH_ADDRESS else "USDC"

    allowance = token.functions.allowance(wallet_address, NPM_ADDRESS).call()
    if allowance >= amount:
        print(f"{token_symbol} already approved")
        return True

    print(f"Approving {token_symbol}...")
    tx = token.functions.approve(NPM_ADDRESS, 2**256 - 1).build_transaction({
        'from': wallet_address,
        'gas': 100000,
        'gasPrice': web3.eth.gas_price,
        'nonce': web3.eth.get_transaction_count(wallet_address),
        'chainId': web3.eth.chain_id
    })

    signed_tx = web3.eth.account.sign_transaction(tx, private_key)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

    print(f"{token_symbol} approval tx: {receipt.transactionHash.hex()}")
    return receipt.status == 1

def create_position_ui_flow_with_rebalance():
    """Create a position following the UI flow with a fixed +/-2% range,
    after rebalancing the wallet first"""
    # Step 0: Rebalance wallet first
    print("\n🚀 Rebalancing wallet before creating position...")
    rebalance_wallet()

    # Give some time for blockchain state to update
    print("Waiting for rebalancing to finalize...")
    time.sleep(5)

    # Step 1: Get pool info
    current_tick, tick_spacing, sqrt_price_x96, eth_price = get_pool_info()

    # Step 2: Calculate the +/-2% tick range
    lower_tick, upper_tick = calculate_two_percent_tick_range(current_tick, tick_spacing)

    print(f"\nUsing fixed +/-2% tick range: {lower_tick} to {upper_tick}")

    # Step 3: Get token balances
    _, weth_balance, usdc_balance, _ = get_wallet_balances()
    print(f"Current balances: {weth_balance} WETH, {usdc_balance} USDC")

    # Calculate 99% of WETH to use for deposit
    balance_factor = Decimal('0.995')  # Use 99.5% of balances
    weth_amount = weth_balance * balance_factor
    print(f"\nUsing {weth_amount:.6f} WETH ({balance_factor * 100}% of balance) for deposit")

    weth_amount_wei = int(weth_amount * Decimal(1e18))

    # Step 4: Calculate optimal token amounts to match Aerodrome UI
    calculated_weth_wei, calculated_usdc_wei = calculate_optimal_amounts(
        weth_amount, lower_tick, upper_tick, current_tick, sqrt_price_x96
    )

    # Convert wei to human-readable amounts
    calculated_weth = Decimal(calculated_weth_wei) / Decimal(1e18)
    calculated_usdc = Decimal(calculated_usdc_wei) / Decimal(1e6)

    print(f"\nOptimal token amounts (matching Aerodrome UI):")
    print(f"WETH: {calculated_weth:.6f}")
    print(f"USDC: {calculated_usdc:.2f}")

    # Check if user has enough USDC
    if calculated_usdc > usdc_balance:
        print(f"Warning: You don't have enough USDC (need {calculated_usdc:.2f}, have {usdc_balance})")
        print("Scaling down amounts to match available USDC...")
        # Scale down both tokens proportionally to match available USDC
        scaling_factor = (usdc_balance * Decimal('0.99')) / calculated_usdc
        calculated_weth = calculated_weth * scaling_factor
        calculated_weth_wei = int(calculated_weth * Decimal(1e18))
        calculated_usdc = usdc_balance * Decimal('0.99')
        calculated_usdc_wei = int(calculated_usdc * Decimal(1e6))
        print(f"Adjusted amounts:")
        print(f"WETH: {calculated_weth:.6f}")
        print(f"USDC: {calculated_usdc:.2f}")

    # Set minimum amounts with 0.5% slippage
    weth_min = int(Decimal(calculated_weth_wei) * Decimal('0.995'))
    usdc_min = int(Decimal(calculated_usdc_wei) * Decimal('0.995'))

    print("\nProceeding with position creation automatically...")

    # Ensure approvals
    if calculated_weth_wei > 0 and not ensure_approval(weth_token, calculated_weth_wei):
        print("WETH approval failed")
        return False

    if calculated_usdc_wei > 0 and not ensure_approval(usdc_token, calculated_usdc_wei):
        print("USDC approval failed")
        return False

    # Prepare mint parameters
    mint_params = {
        'token0': WETH_ADDRESS,
        'token1': USDC_ADDRESS,
        'tickSpacing': tick_spacing,
        'tickLower': lower_tick,
        'tickUpper': upper_tick,
        'amount0Desired': calculated_weth_wei,
        'amount1Desired': calculated_usdc_wei,
        'amount0Min': weth_min,
        'amount1Min': usdc_min,
        'recipient': wallet_address,
        'deadline': int(time.time() + 3600),
        'sqrtPriceX96': 0
    }

    # Build and send transaction
    try:
        # Using exact same nonce approach as working code
        nonce = web3.eth.get_transaction_count(wallet_address)
        gas_price = int(web3.eth.gas_price * 1.5)  # Higher gas price for faster confirmation

        tx = npm_contract.functions.mint(mint_params).build_transaction({
            'from': wallet_address,
            'gas': 3000000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'value': 0,
            'chainId': web3.eth.chain_id
        })

        print(f"Gas price: {gas_price / 1e9} Gwei")
        print("Sending transaction...")

        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Transaction sent: {tx_hash.hex()}")

        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        print(f"Transaction status: {'Success' if receipt.status else 'Failed'}")

        # Check if balances changed
        _, new_weth, new_usdc, _ = get_wallet_balances()

        weth_diff = weth_balance - new_weth
        usdc_diff = usdc_balance - new_usdc

        print(f"WETH used: {weth_diff}")
        print(f"USDC used: {usdc_diff}")

        if weth_diff > 0 or usdc_diff > 0:
            print("Position created successfully!")
            return True
        else:
            print("Transaction succeeded but no tokens were used. Position may not have been created.")
            return False
    except Exception as e:
        print(f"Error creating transaction: {e}")
        return False

def main():
    print("Aerodrome CL Position Creator - With Auto-Rebalance")
    print("-----------------------------------------------------")
    create_position_ui_flow_with_rebalance()

if __name__ == "__main__":
    main()
