# Implementation Plan: IBKR Positions Import + Reconciliation

## 🎯 Objectif

Importer les positions directement depuis IBKR via Flex Query et les réconcilier avec les positions calculées depuis les transactions.

---

## 📋 Architecture

### Tables Database

```sql
-- Table 1: Positions IBKR (source de vérité)
positions_ibkr (
  id INTEGER PRIMARY KEY,
  symbol TEXT NOT NULL,
  quantity REAL,
  cost_basis_money REAL,      -- Coût total IBKR (avec wash sales)
  cost_basis_price REAL,       -- Prix moyen IBKR
  mark_price REAL,             -- Prix actuel du marché
  position_value REAL,         -- Valeur marché (quantity × mark_price)
  unrealized_pnl REAL,         -- P&L non réalisé
  currency TEXT,
  asset_category TEXT,
  last_updated TIMESTAMP
)

-- Table 2: Positions calculées depuis transactions (pour réconciliation)
positions_calculated (
  id INTEGER PRIMARY KEY,
  symbol TEXT NOT NULL,
  quantity REAL,
  average_price REAL,          -- Calculé avec FIFO
  total_cost REAL,
  transaction_count INTEGER,
  adjusted_count INTEGER,
  last_updated TIMESTAMP
)
```

### Flow de données

```
Flex Query API
    ↓
fetch_flex_trades.py (modifié)
    ↓
├─→ Trades → transactions table
└─→ Positions → positions_ibkr table
    
transactions table
    ↓
calculate_and_save_positions.py
    ↓
positions_calculated table

API /api/positions
    ↓
JOIN positions_ibkr + positions_calculated
    ↓
Frontend (avec réconciliation)
```

---

## 🔧 Étapes d'implémentation

### Étape 1: Renommer table actuelle
**Fichier:** `backend/database/schema.sql`

- [ ] Renommer `positions` → `positions_calculated`
- [ ] Créer table `positions_ibkr`
- [ ] Ajouter index sur `symbol` pour les deux tables

**Script migration:**
```sql
ALTER TABLE positions RENAME TO positions_calculated;
```

---

### Étape 2: Modifier Flex Query parser
**Fichier:** `backend/scripts/fetch_flex_trades.py`

- [ ] Ajouter fonction `parse_positions_from_xml(xml_content)`
- [ ] Parser section `<OpenPositions>` du XML
- [ ] Mapper les champs IBKR:
  - `symbol` → symbol
  - `position` → quantity
  - `costBasisMoney` → cost_basis_money
  - `costBasisPrice` → cost_basis_price
  - `markPrice` → mark_price
  - `positionValue` → position_value
  - `unrealizedPnl` → unrealized_pnl
  - `currency` → currency
  - `assetCategory` → asset_category

- [ ] Ajouter fonction `save_positions_ibkr(positions)`
- [ ] DELETE + INSERT dans `positions_ibkr` (remplace tout)

- [ ] Modifier `fetch_and_import_flex_trades()`:
  - Parser trades (existant)
  - Parser positions (nouveau)
  - Sauvegarder les deux
  - Retourner stats: `{trades: X, positions: Y}`

---

### Étape 3: Modifier calculate_and_save_positions.py
**Fichier:** `backend/scripts/calculate_and_save_positions.py`

- [ ] Modifier pour sauvegarder dans `positions_calculated` au lieu de `positions`
- [ ] Garder la logique FIFO actuelle
- [ ] Pas de changement de logique, juste le nom de la table

---

### Étape 4: Modifier API Positions
**Fichier:** `backend/api/routes/positions.py`

- [ ] Modifier `GET /api/positions`:
  ```python
  # Récupérer positions IBKR
  SELECT * FROM positions_ibkr
  
  # Récupérer positions calculées
  SELECT * FROM positions_calculated
  
  # Joindre et calculer réconciliation
  FOR each position:
    qty_ibkr = position_ibkr.quantity
    qty_calc = position_calculated.quantity
    qty_diff = qty_ibkr - qty_calc
    qty_diff_pct = (qty_diff / qty_ibkr) * 100
    
    rec_status = "match" if abs(qty_diff_pct) < 1
                 else "warning" if abs(qty_diff_pct) < 5
                 else "error"
  ```

- [ ] Retourner format:
  ```json
  {
    "positions": [
      {
        "symbol": "SOFI",
        "quantity": 734,
        "cost_basis_money": 14952.30,
        "cost_basis_price": 20.37,
        "mark_price": 15.24,
        "position_value": 11186.16,
        "unrealized_pnl": -3766.14,
        "qty_calculated": 734,
        "qty_diff": 0,
        "qty_diff_pct": 0,
        "rec_status": "match"
      }
    ],
    "summary": {
      "total_positions": 15,
      "matched": 13,
      "warnings": 1,
      "errors": 1
    }
  }
  ```

- [ ] Garder endpoint `POST /api/positions/refresh` (recalcule positions_calculated)

---

### Étape 5: Modifier Frontend - Onglet Load
**Fichier:** `frontend/app/page.tsx`

- [ ] Modifier `handleFlexImport()`:
  - Afficher "Importing trades and positions..."
  - Après succès: "✅ Imported X trades, Y positions"

- [ ] Pas de changement UI, juste le message de confirmation

---

### Étape 6: Modifier Frontend - Onglet Positions
**Fichier:** `frontend/app/page.tsx`

- [ ] Modifier interface `Position`:
  ```typescript
  interface Position {
    symbol: string;
    quantity: number;
    cost_basis_money: number;
    cost_basis_price: number;
    mark_price: number;
    position_value: number;
    unrealized_pnl: number;
    qty_calculated: number;
    qty_diff: number;
    qty_diff_pct: number;
    rec_status: 'match' | 'warning' | 'error';
  }
  ```

- [ ] Modifier tableau Positions:
  - Colonnes: Symbol | Qty | Cost Basis | Market Value | Unreal. P&L | Qty Rec
  - Colonne "Qty Rec":
    - ✅ Vert si `rec_status === 'match'`
    - ⚠️ Orange si `rec_status === 'warning'` (afficher qty_diff)
    - ❌ Rouge si `rec_status === 'error'` (afficher qty_diff)

- [ ] Garder bouton "Refresh Positions" (appelle `/api/positions/refresh`)

- [ ] Ajouter summary cards:
  - Total Positions
  - Matched (✅)
  - Warnings (⚠️)
  - Errors (❌)

---

## 🧪 Tests

### Test 1: Import Flex Query
- [ ] Cliquer "Last Month" dans Load
- [ ] Vérifier que trades ET positions sont importés
- [ ] Vérifier message: "✅ Imported X trades, Y positions"

### Test 2: Affichage Positions
- [ ] Aller dans onglet Positions
- [ ] Vérifier que les données IBKR s'affichent
- [ ] Vérifier colonne "Qty Rec" avec indicateurs ✅⚠️❌

### Test 3: Réconciliation
- [ ] Vérifier que BK montre ✅ (match parfait)
- [ ] Vérifier que SOFI/TSLA montrent ⚠️ ou ❌ si écart
- [ ] Cliquer sur une ligne avec ⚠️ pour voir le détail

### Test 4: Refresh Positions
- [ ] Cliquer "Refresh Positions"
- [ ] Vérifier que positions_calculated est recalculé
- [ ] Vérifier que réconciliation est mise à jour

---

## 📝 Ordre d'exécution

1. ✅ Étape 1: Migration DB (renommer table)
2. ✅ Étape 2: Parser Flex Query positions
3. ✅ Étape 3: Modifier calculate_and_save_positions.py
4. ✅ Étape 4: Modifier API
5. ✅ Étape 5: Modifier Frontend Load
6. ✅ Étape 6: Modifier Frontend Positions
7. ✅ Tests

---

## ⚠️ Points d'attention

1. **Ne pas casser l'existant** - Les boutons Load doivent continuer à fonctionner
2. **Migration DB** - Faire backup avant de renommer la table
3. **Flex Query** - Vérifier que la section OpenPositions est bien dans le XML
4. **Performance** - JOIN positions_ibkr + positions_calculated peut être lent si beaucoup de symboles

---

## 🎯 Résultat Final

**Onglet Load:**
- Boutons "Last Year" / "Last Month" chargent trades + positions
- Message: "✅ Imported 450 trades, 15 positions"

**Onglet Positions:**
- Affiche positions IBKR (source de vérité)
- Colonne "Qty Rec" montre si les transactions sont complètes
- ✅ = Tout bon
- ⚠️ = Petit écart (< 5%)
- ❌ = Gros écart (> 5%) → Transactions manquantes!

**Pas de prise de tête avec avg cost price** - On utilise celui d'IBKR directement.
