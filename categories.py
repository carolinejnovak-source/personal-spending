CATEGORIES = {
    "Automotive":                       {"color": "#64748b", "subcategories": ["Gas", "Parking", "Ubers & Lyfts"]},
    "Bills & Utilities":                {"color": "#0ea5e9", "subcategories": []},
    "Education":                        {"color": "#8b5cf6", "subcategories": ["Museums"]},
    "Entertainment":                    {"color": "#f43f5e", "subcategories": ["Kids Entertainment", "Parent Entertainment"]},
    "Fees & Adjustments":               {"color": "#94a3b8", "subcategories": []},
    "Food & Drink":                     {"color": "#f97316", "subcategories": []},
    "Gas":                              {"color": "#eab308", "subcategories": []},
    "Gifts & Donations":                {"color": "#ec4899", "subcategories": ["Gifts for Friends", "Gifts for Family", "Charitable Donations"]},
    "Groceries":                        {"color": "#22c55e", "subcategories": []},
    "Health & Wellness":                {"color": "#ef4444", "subcategories": ["Pharmacy", "Deductible & Coinsurance", "Copays", "Fitness", "Kids Dental", "Adult Dental"]},
    "Home":                             {"color": "#06b6d4", "subcategories": []},
    "Kids":                             {"color": "#a855f7", "subcategories": ["Extracurriculars", "Educational Materials & Art", "Gifts"]},
    "Miscellaneous":                    {"color": "#d1d5db", "subcategories": []},
    "Personal":                         {"color": "#6366f1", "subcategories": ["Beauty"]},
    "Professional Services":            {"color": "#14b8a6", "subcategories": []},
    "Shopping":                         {"color": "#7c3aed", "subcategories": ["Kids Clothing", "Mom Clothing", "Home"]},
    "Travel":                           {"color": "#1d4ed8", "subcategories": ["Flights", "Hotels", "Dining"]},
}

SUBCATEGORY_COLORS = {
    # Shopping
    "Kids Clothing": "#c084fc", "Mom Clothing": "#a78bfa", "Home": "#818cf8",
    # Gifts & Donations
    "Gifts for Friends": "#f9a8d4", "Gifts for Family": "#f472b6", "Charitable Donations": "#db2777",
    # Travel
    "Flights": "#93c5fd", "Hotels": "#60a5fa", "Dining": "#3b82f6",
    # Automotive
    "Gas": "#94a3b8", "Parking": "#64748b", "Ubers & Lyfts": "#475569",
    # Health & Wellness
    "Pharmacy": "#fca5a5", "Deductible & Coinsurance": "#f87171", "Copays": "#fda4af", "Fitness": "#fb923c", "Kids Dental": "#f9a8d4", "Adult Dental": "#f472b6",
    # Entertainment
    "Kids Entertainment": "#fb7185", "Parent Entertainment": "#f43f5e",
    # Education
    "Museums": "#a78bfa",
    # Personal
    "Beauty": "#818cf8",
    # Kids
    "Extracurriculars": "#c084fc", "Educational Materials & Art": "#a855f7", "Gifts": "#f472b6",
}

CHASE_CATEGORY_MAP = {
    "Automotive": "Automotive",
    "Bills & Utilities": "Bills & Utilities",
    "Education": "Education",
    "Entertainment": "Entertainment",
    "Fees & Adjustments": "Fees & Adjustments",
    "Food & Drink": "Food & Drink",
    "Gas": "Gas",
    "Gifts & Donations": "Gifts & Donations",
    "Groceries": "Groceries",
    "Health & Wellness": "Health & Wellness",
    "Home": "Home",
    "Miscellaneous": "Miscellaneous",
    "Personal": "Personal",
    "Professional Services": "Professional Services",
    "Shopping": "Shopping",
    "Travel": "Travel",
}

def auto_detect_subcategory(category, description):
    d = description.lower()
    if category == "Shopping":
        if any(k in d for k in ["carter", "children's place", "gap kids", "gymboree", "osh kosh", "zara kids", "hanna andersson", "mini boden", "janie and jack", "primary.com", "tea collection"]):
            return "Kids Clothing"
        if any(k in d for k in ["wayfair", "west elm", "pottery barn", "crate and barrel", "cb2", "restoration hardware", "article.com"]):
            return "Home"
        if any(k in d for k in ["anthropologie", "free people", "revolve", "asos", "nordstrom", "bloomingdale", "saks", "neiman", "banana republic", "j.crew", "ann taylor", "loft ", "white house"]):
            return "Mom Clothing"
        return None

    if category == "Travel":
        if any(k in d for k in ["united", "delta", "american air", "southwest", "jetblue", "spirit air", "frontier", "alaska air", "british air", "lufthansa", "emirates", "airways", "airlines", "tsa ", "airport"]):
            return "Flights"
        if any(k in d for k in ["hotel", "marriott", "hilton", "hyatt", "airbnb", "westin", "sheraton", "courtyard", "hampton inn", "doubletree", "holiday inn", "radisson", "four seasons", "ritz", "w hotel", "kimpton", "loews", "mgm hotel", "caesars"]):
            return "Hotels"
        if any(k in d for k in ["restaurant", "cafe", "kitchen", "grill", "bistro", "eatery", "diner", "steakhouse", "sushi", "pizza", "burger", "taco", "thai", "italian", "mexican", "bar & grill", "tavern", "chophouse"]):
            return "Dining"
        return None

    if category == "Gifts & Donations":
        if any(k in d for k in ["charity", "nonprofit", "foundation", "gofundme", "red cross", "unicef", "habitat", "cancer", "heart assoc", "church", "synagogue", "mosque", "temple", "donation"]):
            return "Charitable Donations"
        return None

    return None
