# ruff: noqa

from langchain_google_genai import ChatGoogleGenerativeAI

# 1. Initialize the Gemini model
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

# 2. Define your prompt

prompt = """
You are an expert logistics coordinator. Your **sole responsibility** is to provide the most efficient driver routes as a JSON object. Do not include "```json" in the response, just the raw json.

<instructions>
1.  Analyze the provided pickups, driver capacities, and the locations_matrix to determine optimal routes.
2.  Adhere strictly to the following priorities:
    a. All pickups must be assigned.
    b. Driver capacity cannot be exceeded (capacity is for PEOPLE).
    c. Total driving time must be minimized.
    d. The minimum number of drivers must be used, unless the total drive time is over 11 minutes, then use another driver if available.
3.  Here are preferences. If it is possible, adhere to these preferences.
    a. If the is driver availability, have the person driving to Rita only drive to Rita
    b. If able, a car should stick to a zone. Zones: Rita and Eighth should be grouped together; Revelle, Muir, Sixth, Marshall, ERC, Seventh should be grouped together; Warren, Innovation, and Pepper Canyon should be grouped together;
    c. If able, keep people from the same location together in one car. If this requires moving drivers around so that a driver with more capacity services different people, then make that change.
4.  The final output **MUST be a single JSON object** with driver names as keys and an ordered list of pickup locations as values.
5.  **DO NOT** include any other text, explanations, or code blocks.
6.  If a matching is not possible, give the following output:
    {{
        "error": "reason for error"
    }}
</instructions>

<current_situation>
<pickups>
{pickups_str}
</pickups>
<drivers>
{drivers_str}
</drivers>
<matrix>
{locations_matrix}
</matrix>
</current_situation>

Example of a correct final output:
{{
  "DriverA": [("name1", "Rita"), ("name2", "ERC")],
  "DriverB": [("name3", "Innovation")]
}}

Begin.
"""

locations_matrix = locations_matrix = {
    "Muir": [("Sixth", 2)],
    "Sixth": [("Muir", 2), ("ERC", 3)],
    "ERC": [("Sixth", 3), ("Seventh", 2)],
    "Seventh": [("ERC", 2), ("Warren", 5), ("Innovation", 5)],
    "Warren": [("Seventh", 5), ("Rita", 10), ("Innovation", 1)],
    "Rita": [("Warren", 10), ("Innovation", 10)],
    "Innovation": [("Warren", 1), ("Rita", 10), ("Seventh", 5)],
}

# 3. Invoke the model and get the result
result = llm.invoke(
    prompt.format(
        pickups_str="""
🏫 [8] Scholars (no Eighth)
(2) seventh: carly, irene
(1) erc: clement, kristi
(2) muir: charis, rosalyn
(2) sixth: alice, emily p
🏠 [3] Warren + Pepper Canyon
(2) warren (equality ln): nathan leung, emily yip
(1) pcyn (innovation ln): josh k
🏡 [2] Rita + Eighth
(2) rita: hannah ng, kendra
""",
        drivers_str="1 has capacity 4, 2 has capacity 4, 3 has capacity 1, 4 has capacity 3, 5 has capacity 4",
        locations_matrix=locations_matrix,
    )
)

# 4. Print the content of the response
print(result.content)
print("------------------")
import json

print(json.loads(result.content))
