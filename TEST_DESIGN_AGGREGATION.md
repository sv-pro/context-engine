# Test Design: The Shadow Board (Distributed Aggregation)

## Objective
Verify that the Context Engine can answer a question where the answer requires **aggregating** information from multiple disparate documents, none of which contain the full answer.

## Scenario
The user asks: **"Who are the current members of the Shadow Board?"**

## The Data Chain
1.  **Root Document**: `shadow_board_structure.md`
    -   Content: "The Shadow Board is composed of the current active leaders of three covert divisions: [[Obsidian Vanguard]], [[Cipher Bureau]], and [[Echo Station]]."
    -   *Crucial*: It does NOT list the leaders' names, only the divisions.

2.  **Branch Document A**: `obsidian_vanguard.md`
    -   Content: "The Obsidian Vanguard is a paramilitary unit... currently led by **Director Kael**."
    
3.  **Branch Document B**: `cipher_bureau.md`
    -   Content: "The Cipher Bureau handles cryptography... Under the stewardship of **Head Cryptographer Elara**, it has cracked the code."
    
4.  **Branch Document C**: `echo_station.md`
    -   Content: "Echo Station is a listening post... **Commander Voss** has recently taken command."

## Expected "Reasoning" Flow
1.  **Retrieval Round 1**: 
    -   Query "Shadow Board" matches `shadow_board_structure.md`.
    -   System extracts links: `[[Obsidian Vanguard]]`, `[[Cipher Bureau]]`, `[[Echo Station]]`.
2.  **Retrieval Round 2**:
    -   System follows links to fetch `obsidian_vanguard.md`, `cipher_bureau.md`, `echo_station.md`.
3.  **Synthesis**:
    -   LLM receives context containing all 4 documents.
    -   LLM infers: "Leaders of (Obsidian, Cipher, Echo) = (Kael, Elara, Voss)".
    -   LLM constructs answer: "The members are Director Kael, Head Cryptographer Elara, and Commander Voss."

## Failure Condition
-   System returns only the list of divisions ("It consists of leaders of Obsidian, Cipher, Echo").
-   System misses one or more leaders.
-   System hallucinates names not in text.
