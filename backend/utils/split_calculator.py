"""
Split Calculator Utility - IBKR Portfolio Tracker

Handles stock split and spin-off calculations for transaction adjustments.

⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md
"""

import logging
from typing import List, Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


def calculate_split_adjustment(quantity: float, price: float, ratio: float) -> Tuple[float, float]:
    """
    Calculate adjusted quantity and price based on split ratio.
    
    Args:
        quantity: Original quantity
        price: Original price
        ratio: Split ratio (e.g., 4.0 for 4:1 split, 0.25 for 1:4 reverse split)
    
    Returns:
        Tuple of (updated_quantity, updated_price)
    
    Examples:
        >>> calculate_split_adjustment(10, 400, 4.0)
        (40.0, 100.0)
        
        >>> calculate_split_adjustment(40, 100, 0.25)
        (10.0, 400.0)
    """
    if ratio <= 0:
        raise ValueError(f"Invalid split ratio: {ratio}. Must be > 0")
    
    updated_quantity = quantity * ratio
    updated_price = price / ratio
    
    return updated_quantity, updated_price


def apply_splits_to_transactions(
    symbol: str,
    splits: List[Dict],
    transactions: List[Dict]
) -> List[Dict]:
    """
    Apply multiple splits to transactions in chronological order.
    
    Args:
        symbol: Security symbol
        splits: List of split dicts with keys: id, ex_date, split_ratio, ca_type
                Sorted by ex_date (oldest first)
        transactions: List of transaction dicts with keys: transaction_id, trade_date, quantity, t_price
    
    Returns:
        List of updated transaction dicts with keys:
            - transaction_id
            - symbol
            - trade_date
            - original_quantity
            - original_price
            - updated_quantity
            - updated_price
            - split_ratio (cumulative)
            - ca_id
            - ca_type
            - ca_date
    
    Logic:
        - For each split, apply to transactions BEFORE the split date
        - Multiple splits are cumulative (apply all in order)
    """
    if not splits:
        logger.info(f"No splits to apply for {symbol}")
        return []
    
    if not transactions:
        logger.info(f"No transactions to update for {symbol}")
        return []
    
    # Sort splits by date (oldest first)
    sorted_splits = sorted(splits, key=lambda s: s['ex_date'])
    
    # Sort transactions by date
    sorted_transactions = sorted(transactions, key=lambda t: t['trade_date'])
    
    updated_transactions = []
    
    logger.info(f"📊 Applying {len(sorted_splits)} split(s) to {len(sorted_transactions)} transaction(s) for {symbol}")
    
    for split in sorted_splits:
        split_date = split['ex_date']
        split_ratio = split['split_ratio']
        ca_id = split['id']
        ca_type = split['ca_type']
        
        logger.info(f"   🔄 Split on {split_date}: ratio={split_ratio} ({ca_type})")
        
        # Apply this split to all transactions before the split date
        for tx in sorted_transactions:
            trade_date = tx['trade_date']
            
            # Only apply to transactions BEFORE the split date
            if trade_date < split_date:
                original_qty = tx['quantity']
                original_price = tx['t_price']
                
                # Calculate adjusted values
                updated_qty, updated_price = calculate_split_adjustment(
                    original_qty,
                    original_price,
                    split_ratio
                )
                
                # Check if this transaction already has an updated record
                existing = next(
                    (ut for ut in updated_transactions if ut['transaction_id'] == tx['transaction_id']),
                    None
                )
                
                if existing:
                    # Apply cumulative split from original values
                    cumulative_ratio = existing['split_ratio'] * split_ratio
                    updated_qty, updated_price = calculate_split_adjustment(
                        existing['original_quantity'],
                        existing['original_price'],
                        cumulative_ratio
                    )
                    existing['updated_quantity'] = updated_qty
                    existing['updated_price'] = updated_price
                    existing['split_ratio'] = cumulative_ratio
                    logger.debug(f"      ✏️  Updated {tx['transaction_id']}: {existing['original_quantity']} → {updated_qty} (cumulative ratio={cumulative_ratio})")
                else:
                    # Create new updated transaction record
                    updated_tx = {
                        'transaction_id': tx['transaction_id'],
                        'symbol': symbol,
                        'trade_date': trade_date,
                        'original_quantity': original_qty,
                        'original_price': original_price,
                        'updated_quantity': updated_qty,
                        'updated_price': updated_price,
                        'split_ratio': split_ratio,
                        'ca_id': ca_id,
                        'ca_type': ca_type,
                        'ca_date': split_date
                    }
                    updated_transactions.append(updated_tx)
                    logger.debug(f"      ➕ Added {tx['transaction_id']}: {original_qty} → {updated_qty}")
    
    logger.info(f"✅ Created {len(updated_transactions)} updated transaction(s) for {symbol}")
    
    return updated_transactions


def validate_split_adjustment(original_qty: float, original_price: float, 
                              updated_qty: float, updated_price: float) -> bool:
    """
    Validate that split adjustment preserves total position value.
    
    Args:
        original_qty: Original quantity
        original_price: Original price
        updated_qty: Updated quantity
        updated_price: Updated price
    
    Returns:
        True if total value is preserved (within 0.01% tolerance)
    """
    original_value = original_qty * original_price
    updated_value = updated_qty * updated_price
    
    # Allow 0.01% tolerance for floating point errors
    tolerance = original_value * 0.0001
    
    is_valid = abs(original_value - updated_value) <= tolerance
    
    if not is_valid:
        logger.warning(
            f"⚠️  Split adjustment validation failed: "
            f"original={original_value:.2f}, updated={updated_value:.2f}, "
            f"diff={abs(original_value - updated_value):.2f}"
        )
    
    return is_valid


if __name__ == "__main__":
    # Test cases
    print("Testing split_calculator.py")
    print("=" * 60)
    
    # Test 1: Simple 4:1 split
    print("\n1. Split 4:1 (ratio=4.0)")
    qty, price = calculate_split_adjustment(10, 400, 4.0)
    print(f"   10 shares @ $400 → {qty} shares @ ${price}")
    assert qty == 40.0 and price == 100.0
    assert validate_split_adjustment(10, 400, qty, price)
    print("   ✅ PASS")
    
    # Test 2: Reverse split 1:4
    print("\n2. Reverse Split 1:4 (ratio=0.25)")
    qty, price = calculate_split_adjustment(40, 100, 0.25)
    print(f"   40 shares @ $100 → {qty} shares @ ${price}")
    assert qty == 10.0 and price == 400.0
    assert validate_split_adjustment(40, 100, qty, price)
    print("   ✅ PASS")
    
    # Test 3: Multiple splits
    print("\n3. Multiple splits (cumulative)")
    splits = [
        {'id': 1, 'ex_date': '2020-08-28', 'split_ratio': 4.0, 'ca_type': 'split'},
        {'id': 2, 'ex_date': '2022-06-06', 'split_ratio': 20.0, 'ca_type': 'split'}
    ]
    transactions = [
        {'transaction_id': 'TX001', 'trade_date': '2020-01-01', 'quantity': 10, 't_price': 400},
        {'transaction_id': 'TX002', 'trade_date': '2021-01-01', 'quantity': 40, 't_price': 100},
        {'transaction_id': 'TX003', 'trade_date': '2023-01-01', 'quantity': 800, 't_price': 5}
    ]
    
    updated = apply_splits_to_transactions('AAPL', splits, transactions)
    print(f"   Updated {len(updated)} transactions")
    
    # TX001: before both splits → 10 × 4 × 20 = 800 shares
    tx1 = next(ut for ut in updated if ut['transaction_id'] == 'TX001')
    print(f"   TX001: {tx1['original_quantity']} → {tx1['updated_quantity']} (ratio={tx1['split_ratio']})")
    assert tx1['updated_quantity'] == 800.0
    
    # TX002: before second split only → 40 × 20 = 800 shares
    tx2 = next(ut for ut in updated if ut['transaction_id'] == 'TX002')
    print(f"   TX002: {tx2['original_quantity']} → {tx2['updated_quantity']} (ratio={tx2['split_ratio']})")
    assert tx2['updated_quantity'] == 800.0
    
    # TX003: after both splits → not in updated list
    tx3_exists = any(ut['transaction_id'] == 'TX003' for ut in updated)
    print(f"   TX003: Not updated (after splits)")
    assert not tx3_exists
    
    print("   ✅ PASS")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
