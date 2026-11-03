from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    id: str
    name_en: str
    name_bn: str
    unit: str  # "kg", "litre", "piece", "packet"
    price: int  # rupees per unit (sample data for the demo store)
    stock: float
    aliases: tuple[str, ...]


# Sample demo catalogue. Generic words such as "তেল" or "ডাল" are deliberately
# listed as aliases of several products: the matcher treats them as ambiguous
# and the app must ask "which one?" instead of guessing.
PRODUCTS: list[Product] = [
    Product("atta", "Atta (wheat flour)", "আটা", "kg", 45, 50,
            ("atta", "আটা", "গমের আটা", "gomer atta", "ata", "aata", "आटा")),
    Product("sugar", "Sugar", "চিনি", "kg", 48, 40,
            ("sugar", "chini", "চিনি", "cheeni", "चीनी")),
    Product("rice", "Rice", "চাল", "kg", 52, 100,
            ("rice", "chal", "চাল", "bhat chal", "chawal", "चावल")),
    Product("salt", "Salt", "নুন", "kg", 22, 40,
            ("salt", "nun", "নুন", "লবণ", "labon", "namak", "नमक")),
    Product("mustard_oil", "Mustard oil", "সরষের তেল", "litre", 165, 20,
            ("mustard oil", "sorshe tel", "sorser tel", "sarson tel",
             "সরষের তেল", "সর্ষের তেল", "তেল", "tel", "oil", "तेल", "sarson ka tel")),
    Product("sunflower_oil", "Sunflower oil", "সানফ্লাওয়ার তেল", "litre", 135, 20,
            ("sunflower oil", "sunflower tel", "refined tel", "সানফ্লাওয়ার তেল",
             "রিফাইন্ড তেল", "তেল", "tel", "oil", "तेल")),
    Product("masoor_dal", "Masoor dal", "মসুর ডাল", "kg", 95, 25,
            ("masoor dal", "masur dal", "মসুর ডাল", "ডাল", "dal", "मसूर दाल", "दाल")),
    Product("moong_dal", "Moong dal", "মুগ ডাল", "kg", 120, 20,
            ("moong dal", "mug dal", "মুগ ডাল", "ডাল", "dal", "मूंग दाल", "दाल")),
    Product("tea", "Tea (loose)", "চা পাতা", "packet", 60, 30,
            ("tea", "cha", "চা", "চা পাতা", "cha pata", "chai", "चाय")),
    Product("biscuit", "Biscuits", "বিস্কুট", "packet", 10, 60,
            ("biscuit", "biscuits", "বিস্কুট", "बिस्किट")),
    Product("soap", "Soap", "সাবান", "piece", 35, 30,
            ("soap", "sabun", "সাবান", "साबुन")),
    Product("milk", "Milk packet", "দুধ", "packet", 28, 25,
            ("milk", "dudh", "দুধ", "doodh", "दूध")),
    Product("egg", "Eggs", "ডিম", "piece", 7, 120,
            ("egg", "eggs", "dim", "ডিম", "anda", "अंडा")),
    Product("potato", "Potato", "আলু", "kg", 30, 80,
            ("potato", "alu", "aloo", "আলু", "आलू")),
    Product("onion", "Onion", "পেঁয়াজ", "kg", 40, 70,
            ("onion", "peyaj", "piyaj", "পেঁয়াজ", "পেয়াজ", "pyaaz", "प्याज")),
]

BY_ID: dict[str, Product] = {p.id: p for p in PRODUCTS}
