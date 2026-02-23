import re

text = """Alarm 2236
Oil pressure measuring defective
Cause: Usually followed by an index, 0 = you already have had a oil pressure measuring fault
1 = internal hard ware error
2 = if the pressure does not change by P243 (0.5bar) and
T241 then we get this alarm.
3 = after first charge of the accumulator if the pressure then drops
below P246 then we get this alarm
4 = If the pressure goes above P823 during the time T815
Reaction: unable to switch on pump until fault cured. If you get index 0 then you need to power off/on of
machine
Remedy: check PLC memory
Alarm 2237
Another fault
Cause: Something else
"""

pattern3 = re.compile(
    r'^[ \t]*(?:Alarm|Error|Fault)[ \t]*[:\-]?[ \t]*(\d{1,5})[ \t\.\-\:]*(?:.*?)\n(.*?)(?:\n[ \t]*Cause:[ \t]*(.*?))?(?:\n[ \t]*(?:Reaction|Remedy|Action):[ \t]*(.*?))?(?=\n[ \t]*(?:Alarm|Error|Fault)[ \t]*[:\-]?[ \t]*\d{1,5}|\Z)',
    re.IGNORECASE | re.DOTALL | re.MULTILINE
)

print("\n--- PATTERN 3 ---")
for m in pattern3.finditer(text):
    print(f"ID: {m.group(1)} | DESC: {m.group(2).split(chr(10))[0] if m.group(2) else ''}")
    print(f"CAUSE: {repr(m.group(3))}")
    print(f"ACTION: {repr(m.group(4))}")
