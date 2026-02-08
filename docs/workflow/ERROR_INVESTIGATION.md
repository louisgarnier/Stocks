# Best Practices - Investigation d'Erreurs

## ⚠️ CRITICAL: Lire avant de résoudre une erreur

Ce document contient les leçons apprises lors de l'investigation d'erreurs complexes, notamment les problèmes de récursion avec Pydantic.

---

## 🎯 Principes Fondamentaux

### 1. **Simplifier AVANT de Complexifier**

**❌ MAUVAISE APPROCHE :**
- Ajouter des solutions complexes (forward references, `model_rebuild()`, `from __future__ import annotations`)
- Chercher des solutions avancées avant d'avoir testé la version simple

**✅ BONNE APPROCHE :**
- Créer d'abord une version minimale qui fonctionne
- Ajouter progressivement les fonctionnalités
- Tester à chaque étape

**Exemple :**
```python
# ❌ Commencer avec tout
class LoanPaymentBase(BaseModel):
    date: date = Field(..., description="Date de la mensualité")
    capital: float = Field(..., description="Montant du capital remboursé")
    # ... beaucoup de descriptions

# ✅ Commencer simple
class LoanPaymentBase(BaseModel):
    date: date
    capital: float
    # Ajouter les descriptions après avoir vérifié que ça fonctionne
```

---

### 2. **Comparer avec le Code Existant**

**❌ MAUVAISE APPROCHE :**
- Créer du nouveau code sans regarder comment c'est fait ailleurs
- Supposer que tous les patterns fonctionnent de la même manière

**✅ BONNE APPROCHE :**
- Chercher des exemples similaires dans le codebase
- Copier exactement le pattern qui fonctionne
- Ne dévier que si nécessaire et après avoir testé

**Exemple :**
```python
# Regarder comment TransactionListResponse est défini
class TransactionListResponse(BaseModel):
    transactions: List[TransactionResponse]  # Pas de forward reference
    total: int
    page: int = 1
    page_size: int = 100

# Utiliser le même pattern pour LoanPaymentListResponse
class LoanPaymentListResponse(BaseModel):
    items: List[LoanPaymentResponse]  # Même pattern
    total: int
    page: int = 1
    page_size: int = 100
```

---

### 3. **Tester Progressivement**

**❌ MAUVAISE APPROCHE :**
- Créer tous les modèles d'un coup
- Tester seulement à la fin
- Ne pas savoir quel modèle cause le problème

**✅ BONNE APPROCHE :**
- Créer un modèle à la fois
- Tester après chaque ajout
- Identifier immédiatement le modèle problématique

**Exemple :**
```python
# Étape 1 : Créer LoanPaymentBase seul
class LoanPaymentBase(BaseModel):
    date: date
    capital: float
# Test : from backend.api.models import LoanPaymentBase

# Étape 2 : Ajouter LoanPaymentResponse
class LoanPaymentResponse(LoanPaymentBase):
    id: int
# Test : from backend.api.models import LoanPaymentResponse

# Étape 3 : Ajouter LoanPaymentListResponse
class LoanPaymentListResponse(BaseModel):
    items: List[LoanPaymentResponse]
# Test : from backend.api.models import LoanPaymentListResponse
```

---

### 4. **Isoler le Problème**

**❌ MAUVAISE APPROCHE :**
- Modifier plusieurs choses en même temps
- Ne pas savoir quelle modification cause le problème
- Faire des suppositions sans vérifier

**✅ BONNE APPROCHE :**
- Tester si le problème existait avant vos modifications
- Utiliser `git stash` pour isoler vos changements
- Vérifier chaque hypothèse une par une

**Exemple :**
```bash
# Tester si le problème existait avant
git stash
python3 -c "from backend.api.models import TransactionBase"
# Si ça fonctionne, le problème vient de vos modifications

# Restaurer et tester progressivement
git stash pop
# Tester chaque modèle un par un
```

---

### 5. **Ne Pas Casser l'Application**

**❌ MAUVAISE APPROCHE :**
- Continuer à modifier même si l'app ne fonctionne plus
- Ne pas restaurer immédiatement si l'app est cassée
- Essayer plusieurs solutions complexes en même temps

**✅ BONNE APPROCHE :**
- **TOUJOURS** restaurer immédiatement si l'app est cassée
- Utiliser `git checkout` pour revenir à l'état fonctionnel
- Recommencer avec une approche plus simple

**Exemple :**
```bash
# Si l'app ne fonctionne plus, restaurer IMMÉDIATEMENT
git checkout backend/api/models.py

# Vérifier que ça fonctionne
python3 -c "from backend.api.models import TransactionBase"

# Recommencer avec une approche plus simple
```

---

## 🔍 Processus d'Investigation Systématique

### Étape 1 : Comprendre l'Erreur
1. Lire l'erreur complète (pas juste le type)
2. Identifier où elle se produit (import, création, utilisation)
3. Vérifier si c'est une erreur connue (recherche web si nécessaire)

### Étape 2 : Isoler le Problème
1. Tester si le problème existait avant vos modifications
2. Identifier le code exact qui cause le problème
3. Créer un test minimal qui reproduit l'erreur

### Étape 3 : Comparer avec le Code Existant
1. Chercher des exemples similaires dans le codebase
2. Copier exactement le pattern qui fonctionne
3. Ne dévier que si absolument nécessaire

### Étape 4 : Simplifier
1. Retirer toutes les fonctionnalités non essentielles
2. Créer une version minimale qui fonctionne
3. Ajouter progressivement les fonctionnalités

### Étape 5 : Tester à Chaque Étape
1. Tester après chaque modification
2. Ne pas accumuler plusieurs changements non testés
3. Utiliser des tests simples et rapides

---

## 🚨 Erreurs Courantes à Éviter

### 1. **Récursion avec Pydantic**

**Symptôme :** `RecursionError: maximum recursion depth exceeded` lors de l'import

**Causes possibles :**
- Forward references mal gérées
- Descriptions dans `Field()` qui causent des problèmes
- Ordre de définition des modèles
- Interaction entre plusieurs modèles

**Solution :**
1. Simplifier les modèles (retirer les descriptions)
2. Utiliser le même pattern que les modèles existants
3. Tester un modèle à la fois

### 2. **Modifications qui Cassent l'App**

**Symptôme :** L'application ne démarre plus ou ne fonctionne plus

**Solution immédiate :**
```bash
# Restaurer le fichier problématique
git checkout <fichier>

# Vérifier que ça fonctionne
# Recommencer avec une approche plus simple
```

### 3. **Tourner en Rond**

**Symptôme :** Essayer plusieurs solutions complexes sans résultat

**Solution :**
1. **ARRÊTER** immédiatement
2. Restaurer à l'état fonctionnel
3. Recommencer avec une approche plus simple
4. Tester progressivement

---

## 📝 Checklist Avant de Modifier du Code

- [ ] J'ai lu le code existant pour comprendre le pattern
- [ ] J'ai trouvé des exemples similaires dans le codebase
- [ ] Je vais créer une version minimale d'abord
- [ ] Je vais tester après chaque modification
- [ ] Je sais comment restaurer si ça casse
- [ ] Je ne vais pas ajouter de complexité inutile

---

## 🎓 Leçons Apprises (Cas Réel : Pydantic Récursion)

### Ce qui s'est passé :
1. Création de modèles Pydantic avec descriptions dans `Field()`
2. Récursion infinie lors de l'import du module
3. Tentatives de solutions complexes (forward references, `model_rebuild()`, etc.)
4. Application cassée
5. Solution : simplification en retirant les descriptions

### Ce qui aurait dû être fait :
1. ✅ Regarder comment `TransactionListResponse` est défini
2. ✅ Créer une version minimale sans descriptions
3. ✅ Tester après chaque ajout
4. ✅ Restaurer immédiatement quand l'app est cassée
5. ✅ Recommencer avec une approche plus simple

### Résultat :
- Temps perdu : ~30 minutes à tourner en rond
- Temps avec bonne approche : ~5 minutes
- **Leçon : Simplifier AVANT de complexifier**

---

## 🔧 Outils de Vérification

### Script de Vérification Frontend

Un script `docs/workflow/check_frontend_errors.js` a été créé pour vérifier automatiquement :
- ✅ Erreurs de compilation TypeScript
- ✅ Erreurs ESLint
- ✅ Exports manquants
- ✅ Composants manquants
- ✅ Client API valide

**Usage :**
```bash
node docs/workflow/check_frontend_errors.js
```

**⚠️ IMPORTANT :** Toujours exécuter ce script avant de dire que le code est "OK". Ne jamais affirmer que tout fonctionne sans avoir vérifié.

### Script de Vérification des Exports

Un script `scripts/verify_exports.js` vérifie que tous les imports correspondent à des exports existants.

**Usage :**
```bash
node scripts/verify_exports.js
```

---

## 🔗 Références

- [BEST_PRACTICES.md](./BEST_PRACTICES.md) - Pratiques générales du projet
- [GIT_WORKFLOW.md](./GIT_WORKFLOW.md) - Workflow Git

---

**Dernière mise à jour :** 2026-01-11  
**Cas d'étude :** Récursion Pydantic avec modèles LoanPayment
