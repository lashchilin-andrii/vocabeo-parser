import deepl

auth_key = "276b05c1-cae8-4445-a501-831a521abd8b:fx" # replace with your key
deepl_client = deepl.DeepLClient(auth_key)

result = deepl_client.translate_text("Die Zeit", source_lang="DE", target_lang="RU")
print(result.text)