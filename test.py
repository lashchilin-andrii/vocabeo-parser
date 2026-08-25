from deep_translator import MyMemoryTranslator

translated = MyMemoryTranslator(source="en-US", target="ru-RU").translate("house")
print(translated)  # Output: дом