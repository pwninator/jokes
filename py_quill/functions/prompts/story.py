"""LLM prompt for generating children's stories."""

import json
import re
from typing import Any, Collection, Generator

from common import models
from common.models import ReadingLevel
from services import llm_client

_NUM_PAGES = 10

_TEMPERATURE = 1.0

# pylint: disable=line-too-long
_READING_LEVEL_GUIDELINES = {
    # Examples: Goodnight Moon, The Very Hungry Caterpillar (Adjusted for AI generation)
    ReadingLevel.PRE_K: """Write the story at a Pre-K reading level (ages 3-4):
* Use very simple, high-frequency words (mostly CVC words).
* Construct very short sentences (average 4-6 words).
* Focus on concrete concepts: colors, counting (1-5), basic shapes, animals.
* Employ significant repetition in phrases and sentence patterns.
* Describe familiar, everyday situations (playing, eating, sleeping).
* Relate directly to strong visual elements; describe actions clearly.
* Contain simple cause-and-effect (e.g., "The ball rolls. The cat chases.").
* Feature basic emotions like happy, sad, maybe a little scared; avoid complex emotions.
* Use strictly present tense.
* Each page should have ~20-30 words
""",
    # Examples: Brown Bear Brown Bear, Clifford, Dr. Seuss (early) (Adjusted for AI generation)
    ReadingLevel.KINDERGARTEN: """Write the story at a Kindergarten reading level (ages 5-6):
* Use simple sentences (average 5-8 words) and basic sight words (e.g., Dolch Pre-Primer/Primer).
* Describe familiar settings (home, school, park) and common experiences.
* Show clear, direct cause-and-effect relationships.
* Include basic emotions (happy, sad, angry, surprised) and simple social interactions (sharing, playing together).
* Follow a predictable, linear story structure (beginning, middle, end).
* Use primarily present tense, with some simple past tense for completed actions.
* Each page should have 30-50 words
""",
    # Examples: Frog and Toad, Henry and Mudge (Adjusted for AI generation)
    ReadingLevel.FIRST: """Write the story at a 1st Grade reading level (ages 6-7):
* Use short sentences (average 6-10 words) and basic compound sentences (using 'and', 'but', 'so').
* Employ common vocabulary (e.g., Dolch First Grade) and contextually explain slightly challenging words.
* Develop a simple plot with a clear beginning, middle, and end, often in short chapters.
* Describe relatable situations, possibly with some light fantasy elements.
* Include simple problem-solving scenarios (a character faces a simple challenge and finds a solution).
* Focus on clear character actions and dialogue.
* Use past tense commonly.
* Each page should have ~100 words
""",
    # Examples: Magic Tree House (early), Junie B. Jones
    ReadingLevel.SECOND: """Write the story at a 2nd Grade reading level (ages 7-8):
* Utilize simple and compound sentences (average 6-12 words).
* Employ vocabulary beyond basic sight words, using context clues for new words.
* Develop plots with a clear sequence of events across chapters.
* Show character motivations (why characters do what they do) and distinct character voices.
* Include multiple events leading to a resolution.
* Use contractions and possessives.
* Utilize short paragraphs (2-4 sentences).
* Each page should have ~200 words
""",
    # Examples: Charlotte's Web, Ramona Quimby Age 8
    ReadingLevel.THIRD: """Write the story at a 3rd Grade reading level (ages 8-9):
* Utilize varied sentence structures: simple, compound, and basic complex sentences (avg 7-12 words), using conjunctions like 'because', 'if', 'when'.
* Employ descriptive vocabulary (adjectives, adverbs) including multi-syllable words explained by context.
* Develop plots with multiple related events or simple challenges demonstrating character growth.
* Depict character development and motivations.
* Contain age-appropriate humor (e.g., puns, silly situations).
* Utilize short paragraphs (3-5 sentences) focused on one idea.
* Explore themes like friendship, responsibility, dealing with challenges.
* Use primarily past tense narration, clear dialogue formatting.
* Each page should have ~300 words
""",
    # Examples: Because of Winn-Dixie, Harry Potter and the Sorcerer's Stone
    ReadingLevel.FOURTH: """Write the story at a 4th Grade reading level (ages 9-10):
* Utilize complex sentences (avg 9-15 words) and structured paragraphs (3-5 sentences) with topic sentences.
* Employ grade-appropriate advanced vocabulary, including content-specific words.
* Develop plots containing subplots or twists; may include world-building elements.
* Explore character relationships and internal thoughts.
*  Address abstract concepts and themes (e.g., friendship, courage, fairness, belonging) appropriately for the age group.
* Use descriptive language and simple figurative language (similes).
* Each page should have ~300 words
""",
    # Examples: Wonder, Bridge to Terabithia
    ReadingLevel.FIFTH: """Write the story at a 5th Grade reading level (ages 10-11):
* Utilize sophisticated sentence structures (average 11-18 words).
* Employ challenging grade-appropriate vocabulary, including academic terms.
* Develop complex plots with multiple threads and potential symbolism.
* Depict deep character development, internal conflicts, motivations, and realistic flaws.
* Explore abstract themes (loss, identity, empathy) with nuance; handle significant emotional events.
* Use varied figurative language (metaphors, personification).
* Construct well-developed paragraphs presenting clear ideas.
* Each page should have ~300 words
""",
    # Examples: Percy Jackson, Roll of Thunder Hear My Cry
    ReadingLevel.SIXTH: """Write the story at a 6th Grade reading level (ages 11-12):
* Utilize complex and varied sentence structures (average 12-20 words).
* Employ rich, nuanced, specific vocabulary; expect inference from context.
* Develop intricate plots (subplots, flashbacks, foreshadowing); may handle historical or mythological contexts.
* Explore complex character relationships, internal conflicts, and character growth arcs.
* Address sophisticated themes (e.g., identity, justice, prejudice, societal issues, morality) with nuance.
* Use literary devices (metaphor, simile, personification, irony, symbolism) effectively.
* Construct well-organized paragraphs with topic sentences and supporting details.
* Allow for shifts in narrative perspective or voice.
* Each page should have ~300 words
""",
    # Examples: The Giver, The Outsiders
    ReadingLevel.SEVENTH: """Write the story at a 7th Grade reading level (ages 12-13):
* Utilize advanced sentence structures with varied lengths and complexity.
* Employ wide-ranging vocabulary (academic, domain-specific).
* Develop complex narratives (multiple plotlines, internal/external conflicts, resolutions); may use dystopian or specific social settings.
* Explore sophisticated character development (motivations, flaws, changes over time, peer dynamics).
* Address abstract themes (conformity, societal structures, belonging, consequences) with depth.
* Incorporate literary devices (foreshadowing, irony, symbolism) meaningfully.
* Maintain consistent tone and style.
* Each page should have ~300 words
""",
    # Examples: The Book Thief, To Kill a Mockingbird
    ReadingLevel.EIGHTH: """Write the story at an 8th Grade reading level (ages 13-14):
* Utilize highly complex sentences (embedded clauses, modifiers); may feature distinct narrative voice or perspective (e.g., first-person).
* Employ rich vocabulary (advanced academic/technical); convey tone and voice effectively.
* Construct intricate plots (subplots, parallel narratives, complex resolutions); may consider historical context.
* Explore nuanced character development (internal conflicts, moral dilemmas, evolving relationships).
* Address abstract themes (justice, prejudice, morality, loss, historical impact) with subtlety and complexity.
* Incorporate varied literary devices effectively for specific effects.
* Establish distinct narrative voice and style.
* Each page should have ~300 words
""",
    # Examples: Romeo and Juliet, Animal Farm
    ReadingLevel.NINTH: """Write the story at a 9th Grade reading level (ages 14-15):
* Employ sophisticated and varied sentence structures demonstrating syntactic command; may use poetic language.
* Utilize wide-ranging vocabulary (abstract, technical, literary terms).
* Develop complex, multi-layered plots with thematic depth; may use allegory or satire.
* Explore highly developed characters (complex motivations, internal conflicts, significant growth, tragic flaws).
* Address challenging abstract themes (social critique, fate, power, manipulation, philosophical questions).
* Incorporate literary devices skillfully to enhance meaning.
* Establish mature, nuanced narrative voice.
* Aim for approximately 300 words per page (standard chapter/novel format).
""",
    # Examples: Lord of the Flies, Fahrenheit 451
    ReadingLevel.TENTH: """Write the story at a 10th Grade reading level (ages 15-16):
* Employ masterful sentence structure (emphasis/nuance techniques).
* Utilize broad, precise vocabulary attentive to connotation.
* Construct complex plots (subplots, symbolism, thematic resonance); may explore societal critique.
* Develop psychologically nuanced characters (profound motivations, group dynamics, impact of environment).
* Address challenging themes (human nature, censorship, technology's impact, loss of innocence) with ambiguity or complexity.
* Employ literary devices with subtlety and artistry.
* Establish distinctive, compelling narrative voice reflecting intellectual curiosity.
* Each page should have ~300 words
""",
    # Examples: The Great Gatsby, 1984
    ReadingLevel.ELEVENTH: """Write the story at an 11th Grade reading level (ages 16-17):
* Employ highly advanced sentence structures (stylistic variation, rhetoric); may use unreliable narrators.
* Utilize comprehensive, precise vocabulary understanding connotation.
* Construct complex narratives (multiple perspectives, interwoven plotlines, thematic complexity); use symbolism effectively.
* Develop highly nuanced, psychologically complex characters (disillusionment, societal roles).
* Address challenging themes (social class, the American Dream, totalitarianism, existential questions) with ambiguity, irony, or multiple interpretations.
* Employ sophisticated literary devices with artistry and precision.
* Establish distinctive voice reflecting intellectual maturity and critical thinking.
* Each page should have ~300 words
""",
    # Examples: Hamlet, Brave New World, Beloved
    ReadingLevel.TWELFTH: """Write the story at a 12th Grade reading level (ages 17-18):
* Employ advanced sentence structures (mastery of syntax, style, rhetoric); may use non-linear structure or unique stylistic choices (e.g., stream-of-consciousness, magical realism).
* Utilize comprehensive, nuanced vocabulary understanding connotation and etymology.
* Construct highly complex narratives (multiple perspectives, ambiguous endings, philosophical depth).
* Develop exceptionally nuanced characters (profound motivations, moral dilemmas, transformation, exploring the human condition).
* Address challenging abstract themes (existence, memory, trauma, freedom, societal control) with depth, subtlety, irony, prompting deep reflection.
* Employ sophisticated literary devices with originality and precision.
* Establish distinctive, mature narrative voice prompting reflection and discussion.
* Each page should have ~300 words
"""
}


STORY_INSTRUCTIONS_BASE = """**DESIRED STORY QUALITIES:**

*   **RIOTOUSLY FUNNY and ENGAGING:** The story MUST be genuinely funny and engaging for both children and adults, aiming for a Pixar-like tone.  Humor MUST be multifaceted, including:
    *   Visual gags
    *   Situational comedy
    *   Character-driven humor
    *   Clever wit
    *   Cultural references
    *   **Comical Upsets of Expectations:** Deliver humor via unexpected plot twists and reveals that subvert audience expectations.
    *   **Suspenseful Clue-Dropping:**  Drop subtle clues throughout the story that build up to the unexpected comical reveals.
        * Example: Drop hints throughout the story about an ancient dragon that is destroying the forest, but reveal that the dragon is actually just vain, and has been using a new "dragon scale polish" that inadvertently contains a chemical that is killing the forest.
    *   **Logical, Yet Unexpected Reveals:** Ensures reveals are both surprising *and* logically sound within the story's world, creating "wait, what?!" then "actually, that's brilliant!" moments.
    *   **Subversion of Tropes:** Playfully subvert common tropes and clichés for comedic effect.

*   **EPIC in SCOPE:** The story MUST feel like a significant adventure or quest, incorporating:
    *   A clear problem or mystery.
    *   A journey or quest (physical or metaphorical).
    *   Rising action and escalating stakes.
    *   A satisfying climax and resolution.
    *   Meaningful character growth or change.
    *   Unless otherwise specified, the story should be ACTUALLY epic (e.g. stuffed animals can talk/move and travel to faraway places) rather than just reinterpretations of mundane events (e.g. a kitten's "epic" journey to the top of the refrigerator).

*   **MEMORABLE CHARACTERS:**  Develop memorable characters, including the main character, side characters, and antagonists that enhance the humor and plot.
    *   Remain faithful to the provided character descriptions, but you can give them additional traits, abilities, or professions to enhance the humor and plot.
        *   Example: If the main character is a young boy and the story is in a fantasy forest, you can make the boy a ranger even if the original description didn't say that.

*   **PROMPT INTENT and GENRE FAITHFULNESS:**  While creativity and unexpected twists are encouraged, the story **MUST remain faithful to the spirit and implied genre of the STORY PROMPT.**
    *   **Consider the Intent:** The STORY PROMPT was given by someone who commissioned the story. Consider what their expectations are when they gave the prompt, and prioritize interpretations that align with thos expectations.
    *   **Genre Tropes as Starting Point:**  Use genre tropes associated with the STORY PROMPT as a starting point and subvert them playfully, rather than completely discarding them.
    *   **Avoid Semantic Reinterpretation:**  Avoid overly literal or semantic reinterpretations of the STORY PROMPT that deviate significantly from common understanding (e.g., dragons being mushrooms).  Unexpected twists should enhance, not undermine, the core concept of the prompt.
    *   **Surprise WITHIN Expectations:** Aim for surprises and humor that arise from unexpected *twists* and *turns* within the expected genre and theme, rather than fundamentally changing the core elements implied by the prompt.

*   **EXEMPLIFY GOOD BEHAVIOR:**  The story should be a positive role model for children, demonstrating good behavior and values.
    *   **Child Safety:**  Characters should behave safely and responsibly. Examples of unsafe behavior to avoid:
         *  Running into traffic
         *  Wandering off with strangers
         *  Playing with dangerous objects (e.g. guns, knives, fireworks, ovens, etc.)
         *  Playing with fire
         *  Eating dangerous/unknown foods
         *  Touching dangerous animals
         *  Polluting the environment, even if just for fun

*   **POSITIVE AND CHILD-APPROPRIATE MESSAGE:**  The story should have a positive message that is reinforced throughout the story. Avoid anything that is overly negative or dark.
    *   **Avoid mean-spirited humor or negativity:** Maintain a positive humor tone.
        * Example: Name for a team of very low powered superheroes: "The Useless League" is too negative and mean-spirited. "The Slightly Special Forces" is a better name.
    *   **Child appropriate jokes:** Make sure that the jokes are clean and appropriate for children.

*   **APPROPRIATE FOR CHILDREN:**  The story should be appropriate for children.
    *   **Avoid inappropriate content:** Avoid content that is inappropriate for children, including:
        *  Sexual content
        *  Strong language
        *  Alcohol and drug use, and other substance abuse
        *  Gambling
        *  Extreme violence
        *  Any content that is not appropriate for children
"""


_STORY_INSTRUCTIONS = STORY_INSTRUCTIONS_BASE + """
*  **ILLUSTRATION GUIDELINES:** Follow these guidelines when generating illustration descriptions:
    * Illustrations will be generated by AI, which only supports images with up to two characters. Therefore, it is critical that every image contains AT MOST TWO characters.
    * Illustration descriptions will be fed to an AI image generator, which will ONLY see the description text, so it MUST contain all necessary details to generate the image.

*   **MEANINGFULLY INTEGRATED REFERENCE MATERIAL:** The provided reference material MUST be seamlessly woven into the narrative. They MUST:
    *   Be mentioned by name in the story text in an organic and natural way.
    *   Not just stated as facts, but have meaningful impact on the plot.
    *   Be presented in a way that hides the learning aspect (e.g. prefer demonstrations over explanations), so that the children can learn without realizing that they are learning.
    *   Be demonstrated through narrative events and character actions, NOT through dialogue or lectures.
    *   Use simplifications or analogies to help children understand if the topic is too complex, but make sure it's clear how it relates to the original topic.
    *   **Prioritize Narrative Coherence and Impact:** While the reference material must be meaningfully integrated, it is acceptable and even encouraged to have some elements play a more prominent role in the plot than others if doing so creates a more compelling, focused, and coherent story.
"""


_plot_llm = llm_client.get_client(
    label="Reference Material Search Queries",
    model=llm_client.LlmModel.GEMINI_2_5_PRO,
    temperature=_TEMPERATURE,
    thinking_tokens=0,
    output_tokens=4000,
    system_instructions=[
        """You are a creative storyteller specializing in writing epic and riotously funny children's stories that are also engaging and enjoyable for adults, similar in style and tone to Pixar movies.
You have received a commission to write a story based on the given inputs and guidelines.
Your task is to brainstorm ideas and choose the best core concept for the story.

The application will provide you with:

1.  A story prompt: A short description or idea for a children's story.
2.  A list of characters: The names and descriptions of the characters in the story.
3.  A list of your past stories: For variety, create new stories that are distinctly different from your past stories.
4.  A reading level: All of the plot points and concepts should be appropriate for this reading level

Output the following fields in a JSON dictionary:

1.  `user_expectation`: Read the user's story prompt carefully. Summarize the core theme, expected tone (e.g., funny, adventurous), and focus in 1-2 sentences in the `user_expectation` field. 
  * Interpret potentially child-inappropriate themes (like 'fight', 'battle', 'destroy', 'poison') through the lens of child-friendly media (e.g., cartoons like Paw Patrol).
    * Example: Action sequences should be depicted as adventurous, perhaps comical or slapstick, focusing on challenges, problem-solving, and cleverness rather than realistic harm or threat.
    * Example: "Defeat" should mean being outsmarted, temporarily stopped (e.g., tangled up, tricked), or having plans foiled, always ensuring a child-appropriate resolution.
    * Example: "Poison" might mean a substance causing temporary, funny effects (like hiccups or turning purple) rather than actual harm.
  * Avoid overly sanitizing the user's core request for action, but ensure the *portrayal* and *consequences* are suitable for young children. This reinterpreted understanding guides the plot generation.
2.  `plot1`, `plot2`, `plot3`: Based on the reinterpreted user prompt understanding from Step 1 and character descriptions, devise three different brief plot ideas.
  * Aim for concepts that are potentially **epic, adventurous, and genuinely funny, with humor and themes that could appeal to both children and adults** (think Pixar-style broad appeal).
  * Ensure all plot concepts are suitable for young children, avoiding scary or mature themes.
  * Each plot should be a JSON object with the following fields:
    * `plot`: A ~5 sentence description of the plot.
    * `eval`: A brief evaluation of how well the plot fits the above criteria.
4.  `choice_rationale`: Analyze the three plot-title pairs. Choose the single best option based on:
    * **Plot Engagement:** Is the plot concept the most fun, adventurous, and engaging for a children's story, with strong potential for humor and heart?
5.  `chosen_plot`: The string identifier of the chosen plot (e.g., "plot1", "plot2", or "plot3").

**Example Output Format:**

{
  "user_expectation": "The user wants a simple, likely gentle story about a common childhood activity (building a fort) where the character learns through observing nature in their backyard.",
  "plot1": {
    "plot": "Bob tries building a fort with flimsy leaves and twigs, but it keeps collapsing comically. He observes a bird meticulously weaving its sturdy nest nearby. Inspired, Bob learns about the techniques birds use...",
    "eval": "Evaluation..."
  },
  "plot2": {
    "plot": "Bob digs a tunnel under the fence to explore the neighbor's yard, learning about soil composition and stability...",
    "eval": "Evaluation..."
  },
  "plot3": {
    "plot": "Bob uses mud and sticks after a rainstorm to build a structure, learning about natural building materials...",
    "eval": "Evaluation..."
  },
  "choice_rationale": "Plot 1 offers the best ...",
  "chosen_plot": "plot1"
}
"""],
    response_schema={
        "type": "OBJECT",
        "properties": {
            "user_expectation": {"type": "STRING"},
            "plot1": {
                "type": "OBJECT",
                "properties": {
                    "plot": {"type": "STRING"},
                    "eval": {"type": "STRING"}
                },
                "required": ["plot", "eval"],
                "property_ordering": ["plot", "eval"]
            },
            "plot2": {
                "type": "OBJECT",
                "properties": {
                    "plot": {"type": "STRING"},
                    "eval": {"type": "STRING"}
                },
                "required": ["plot", "eval"],
                "property_ordering": ["plot", "eval"]
            },
            "plot3": {
                "type": "OBJECT",
                "properties": {
                    "plot": {"type": "STRING"},
                    "eval": {"type": "STRING"}
                },
                "required": ["plot", "eval"],
                "property_ordering": ["plot", "eval"]
            },
            "choice_rationale": {"type": "STRING"},
            "chosen_plot": {
                "type": "STRING",
                "enum": ["plot1", "plot2", "plot3"],
            }
        },
        "required": [
            "user_expectation", "plot1", "plot2", "plot3", "choice_rationale", "chosen_plot"],
        "property_ordering": [
            "user_expectation", "plot1", "plot2", "plot3", "choice_rationale", "chosen_plot"],
    }
)


_outline_llm_by_model = {
    model: llm_client.get_client(
        label=f"Outline Draft ({model.value})",
        model=model,
        thinking_tokens=0,
        output_tokens=8000,
        temperature=_TEMPERATURE,
        system_instructions=[
            f"""You are a creative storyteller specializing in writing epic and riotously funny children's stories that are also engaging and enjoyable for adults, similar in style and tone to Pixar movies.
You have received a commission to write a story based on the given inputs and guidelines.
Your task is to brainstorm ideas, create characters, and outline the story.

You are given the following by the client:

*  **A story prompt with two versions:** The client has provided two versions of the story prompt. They are two different ways to describe the same story, and both are equally important.
  * This is the central concept or situation around which the story should revolve. Your story may creatively add additional plot elements, characters, settings, etc. that are not directly mentioned in the prompt, but it is critical that everything in the prompt is represented in the story, as long as they are appropriate for children.
  * If it includes any plot elements, such as settings, chØaracters, events, or morals, be sure to include them in the story.
  * If it includes a topic (e.g. just mentioning a topic, or saying that the client wants to learn about that topic, etc.), such as a scientific concept, technology, historical event, etc., make sure that it is meaningfully and accurately represented and demonstrated in the story.
  * Exception: If the prompt contains anything inappropriate for children, such as sexual content, drug use, extreme violence, etc., reinterpret/remove them in a way that is appropriate for children.
*  **A list of characters:** The story must include these characters, but you can also create additional ones.
*  **Topic and reference material:** The client has provided a topic that they want to be a key part of the story, as well as reference material about that topic. Make sure that the topic is accurately and actively represented in the story, using information from the reference material. You may creatively interpret the reference material to make it more engaging and relevant to the story, but the facts, definitions, and concepts about the topic and related topics MUST be accurately depicted.
  * The topic should play a central and active role in the story, not just described in dialogue. For example:
    * If the topic is a place, the story should take place in that place.
    * If the topic is a person, creature, or object, it should physically be in the story.
    * If the topic is a scientific concept or phenomenon, it should be actively demonstrated in the story.
    * If the topic is a historical event, the story should take place during that event.
*  **A target reading level:** All of the plot points and concepts should be appropriate for this reading level.

{_STORY_INSTRUCTIONS}

Output your final answer of the story components, using opening/closing tags to indicate each component:

Tone:
<tone>: The tone of the story. Which combination of Pixar/Dreamworks/Disney/etc. movies is this like?

Reference Material:
<reference>: Choose specific concepts/details from the reference material that will be included in the story, each including the following nested tags:
  * <concept>: The concept, topic, or keyword,
  * <explanation>: The explanation of the concept, written for children, to help them understand the story.
  * <plot>: How the concept will drive the plot forward. Examples:
    * If the concept is about fire, one part could be about the elements of fire (fuel, oxygen, heat), and the main character might need to find all three in order to help a dragon breath fire again.
    * If the concept is about forest layers, the main character might need to travel through each layer, overcoming challenges in each that are related to that layer's biological characteristics, in order to reach the end of their quest.
  * <demonstration>: A 1 sentence explanation of how the concept will be actively demonstrated in the story.
    * Make sure the reader sees the concept in action, not just explained in dialogue.

Title:
<title>: A memorable title of the story.

Tagline:
<tagline>: A tagline that clearly but creatively conveys the learning topic of the story and hooks the reader's interest.

Summary:
<summary>: A 1 sentence summary of the story.

Characters:
<character> (repeated): The named characters in the story, each including the following nested tags:
  * <name>: The name of the character.
  * <visual>: A detailed 1 sentence visual description in enough detail to help the illustrator bring your characters to life, including their physical appearance, posture, demeanor, etc. Color, size, and clothing are important details to include. However, text space is very limited, so keep the descriptions as concise and short as possible.
    * DO NOT include the character's name
    * If they're a person, you MUST include:
      * Age (number or approximate)
      * Hair style and color
      * Skin color
      * Clothing, including color and type (e.g. t-shirt, dress, etc.)
    * Humans must be dressed in modest, child-appropriate clothing.
    * If they're not human, you MUST include:
      * What are they (e.g. dragon, robot, fairy, etc.)? Be as specific as possible (e.g. "dalmation", not "dog")
      * Size
    * Color
    * Details specific to their type, e.g. (does the robot have legs or wheels? does the dragon have horns?)
  * <humor>: A 1-2 sentence explanation of what makes the character funny.
    * For variety, use different humor styles for different characters.

Cover:
<cover_illustration>: Encloses information about the cover illustration feature 1-2 main characters, including:
  * <cover_illustration_character> (repeated): The names of the main characters that are featured in the cover illustration.
    * ONLY include the character name and no other text.
    * Example: In the image "Ignis runs while reading Leafy's map," the cover character should be "Ignis" because he is in the scene, but NOT "Leafy" because he is not.
  * <cover_illustration_description>: A 3-5 sentence description of the cover illustration that features the main character(s) in an engaging, humorous scene that captures the spirit of the story.
    * The story is a comedy, and that should come across in the cover illustration.
    * The title, tagline, and character name of the book will be displayed separately and should NOT be included in the illustration.
    * Include a detailed visual description of the foreground, background, and characters.

Outline:
<outline>: The outline of the story, broken down into phases or acts. Use detailed but concise and to-the-point summaries. For each, use the following nested tags:
  * <phase> (repeated): Encloses nested-tags for the components of this phase:
    * <name>: The name of the phase.
    * <key_plot_points>: Summarize the key plot points, main events, and challenges of this phase.
      Specifically highlight any clues dropped or hints revealed that build suspense in this phase.
    * <humor>: Explains opportunities for humor (visual, situational, character-based, wit) and how the story achieves Pixar-like appeal in this phase.
      Include any specific witty dialogue or remarks, cultural references, or cultural subversions.
      Point out how this phase utilizes suspenseful clue-dropping, comical upsets of expectations, logical reveals, or subversion of tropes for comedic effect.
    * <reference>: Bullet list of actively demonstrated reference material in this phase.

Example final answer output format:

<tone>A blend of Inside Out's emotional depth and humor with Wall-E's environmental message, featuring Toy Story's friendship dynamics and Up's heartwarming adventure.</tone>

<reference>
<concept>Forest Layers</concept>
<explanation>A forest has different layers like a giant layer cake. Each layer has its own special plants and animals that call it home, from the dark forest floor all the way up to the sunny canopy.</explanation>
<plot>Jenny must travel through each forest layer to find magical ingredients, with each layer presenting unique challenges based on its biological characteristics.</plot>
<demonstration>As Jenny climbs through the understory, she encounters shade-loving ferns that demonstrate how plants adapt to low light conditions.</demonstration>
</reference>

<reference>
<concept>Fire Triangle</concept>
<explanation>Fire needs three things to burn: fuel (something to burn), oxygen (from the air), and heat. If any one is missing, there can't be fire!</explanation>
<plot>Ignis can't breathe fire because one element of the fire triangle is missing, and Jenny must help figure out which one.</plot>
<demonstration>Through trial and error with Ignis's fire breathing attempts, readers see how each element of the fire triangle is necessary for fire to exist.</demonstration>
</reference>

<title>The Forest Fire Mystery</title>
<tagline>A blazing adventure through nature's layers!</tagline>
<summary>When dragon Ignis loses his fire-breathing ability in the enchanted forest, Jenny must journey through the forest's layers to discover which part of the fire triangle is missing.</summary>

<character>
<name>Ignis</name>
<visual>A small crimson dragon with gleaming gold scales, sharp obsidian claws, and wisps of white smoke curling from his nostrils, wearing a comically oversized safety helmet.</visual>
<humor>Despite being a dragon, Ignis is hilariously overcautious about fire safety, constantly reciting safety guidelines and carrying a tiny fire extinguisher that's actually filled with glitter.</humor>
</character>

<character>
<name>Jenny</name>
<visual>Jenny is a curious 7-year-old Asian girl with a black ponytail, wearing a forest ranger vest over a green t-shirt and blue jeans, with a magnifying glass hanging from her neck.</visual>
<humor>Jenny's enthusiasm for science leads her to narrate everything like a nature documentary, complete with exaggerated whispers and dramatic pauses at the most inappropriate moments.</humor>
</character>

<character>
<name>Leafy</name>
<visual>Leafy is a young, anthropomorphic green leaf with large expressive eyes and friendly smile. He is always tired.</visual>
<humor>Leafy's humor stems from his naive observations, comically exaggerated physical reactions like fluttering or wilting, and boundless, often misplaced enthusiasm for everyday leaf duties, and speaking with plant-based puns</humor>
</character>

<cover_illustration>
<cover_illustration_character>Ignis</cover_illustration_character>
<cover_illustration_description>Ignis flies through a misty forest, wearing oversized safety goggles as he attempts to breathe fire but produces a stream of rainbow bubbles instead. The forest is dimly lit, but beams of sunlight shine through the dense foliage of the tall, ancient trees, dramatically illuminating the scene.</cover_illustration_description>
</cover_illustration>

<outline>
<phase>
<name>The Mystery Begins</name>
<key_plot_points>
* Jenny discovers Ignis trying (and failing) to breathe fire in the forest
* They realize his fire isn't working but don't know why
* CLUE DROP: Leafy mentions seeing strange mist in the canopy at night
* Jenny hypothesizes they need to check each forest layer for clues
</key_plot_points>
<humor>
Ignis's failed attempts at breathing fire result in increasingly ridiculous outcomes (bubbles, confetti, squeaky toys). Jenny's documentary-style narration of each attempt gets progressively more dramatic, while Leafy keeps interrupting with terrible plant puns ("Looks like this situation is getting pretty tree-cky!").
</humor>
<reference>
* Introduces the fire triangle concept through Ignis's failed attempts
* Shows the basic forest layers through Jenny's initial observations
</reference>
</phase>

<phase>
<name>The Forest Floor Investigation</name>
<key_plot_points>
* Team explores the dark, damp forest floor
* Discover unusual patches where nothing will burn
* CLUE DROP: Find mysterious footprints that sparkle
* Meet a wise old mushroom who hints about "oxygen thieves"
</key_plot_points>
<humor>
Jenny's attempts to interview fungi witnesses leads to hilarious misunderstandings as she can't tell which way they're facing. Ignis insists on wearing water wings because the forest floor is "too moist for dragon safety protocols."
</humor>
<reference>
* Demonstrates decomposition on the forest floor
* Shows how moisture affects fire
* Introduces the role of fungi in the forest ecosystem
</reference>
</phase>
... more phases as needed ...
</outline>
"""
        ],
    )
    for model in llm_client.LlmModel
}


_initial_draft_llm_by_model = {
    model: llm_client.get_client(
        label=f"Initial Draft ({model.value})",
        model=model,
        thinking_tokens=0,
        output_tokens=8000,
        temperature=_TEMPERATURE,
        system_instructions=[
            f"""You are a creative storyteller specializing in writing epic and riotously funny children's stories that are also engaging and enjoyable for adults, similar in style and tone to Pixar movies.
Use the given inputs and guideline below to write the story.

You will be given:

*  A story prompt. This is the central concept or situation around which the story should revolve.
*  Title
*  The tone of the story
*  List of characters
*  Topics/concepts and how they should be used in the story.
*  Reference material you can use to expand on the given topics.
*  A target reading level. Use vocabulary and concepts appropriate for this reading level.
*  Story outline

{_STORY_INSTRUCTIONS}

Output your final answer of the story, broken down into {_NUM_PAGES} pages. For each page, use <page> tags to enclose the following nested tags:
  * <num>: The page number (starting at 1).
  * <humor>: A bullet list of the humor in the page, including witty dialogue, visual gags, situational comedy, character-driven humor, etc.
  * <text>: The story text.
    * The text between <text> and </text> tags will be printed directly on the book, so ONLY include the story text here and nothing else (e.g. no other tags).
  * <illustration_character> (repeated): The name of the 1-2 characters to feature in the illustration
    * ONLY include the character name and no other text.
    * If the illustration has no characters, do not include any <illustration_character> tags.
  * <illustration_description>: A 3-5 sentence description of a humorous illustration of the character(s) that you chose.
    * The description MUST include a detailed visual description of the foreground, background, and characters.
    * The goal of the illustration is to visually amplify the humor described on the page.
    * Focus on depicting the specific moment or action that is most inherently funny or benefits most from a visual representation, like slapstick or an absurd physical situation.

Example final answer output format:

<page>
<num>1</num>
<humor>
* Visual gag: Ignis wearing every possible piece of safety equipment while trying to light a single candle
* Situational comedy: Jenny's documentary-style narration getting interrupted by Ignis's safety briefing
* Character-driven humor: Leafy's terrible attempt at plant puns making everyone groan
</humor>
<illustration_character>Ignis</illustration_character>
<illustration_description>Ignis stands nervously before a birthday candle, wearing a firefighter helmet, three safety vests, and water wings. The cake is covered in white frosting, topped with fruits and a single lit candle, and is set on a wooden table covered in an orange and red tablecloth, surrounded by white plates and napkins. Stacks of colorful wrapped presents can be seen in the background.</illustration_description>
<text>
... text ...
... text ...
</text>
</page>

... other pages ...

<page>
<num>{_NUM_PAGES}</num>
<humor>
* Visual gag: Leafy dramatically falling from a branch in slow motion
* Dialogue humor: Leafy's increasingly desperate plant puns
* Situational comedy: Jenny treating a simple leaf fall like breaking news
</humor>
<illustration_character>Jenny</illustration_character>
<illustration_character>Leafy</illustration_character>
<illustration_description>Jenny is intently looking up at Leafy falling from a tree. She is standing on a green grassy hill with patches of yellow and white wild flowers. The tree, a tall, old oak, with long branches and thick foliage, can be seen in the background, with a clear blue sky above.</illustration_description>
<text>
... text ...
... text ...
... text ...
</text>
</page>
"""
        ],
    )
    for model in llm_client.LlmModel
}


def generate_plot(
    story_prompt: str,
    characters: list[models.Character],
    past_story_titles: list[str],
    reading_level: int,
    extra_log_data: dict[str, Any],
) -> tuple[str, str, dict[str, str], models.SingleGenerationMetadata]:
  """Generate a story plot.

  Args:
      story_prompt: The story prompt to find reference material for
      characters: Optional list of characters to consider for topic selection
      past_story_titles: Optional list of story titles to avoid repetition
      reading_level: Reading level of the story
      extra_log_data: Extra log data to include in the log

  Returns:
      Tuple of (plot, response dictionary, generation metadata)

  Raises:
      ValueError: If no queries could be generated
  """

  prompt_parts = _get_base_prompt_parts(
      user_guidelines=None,
      reading_level=reading_level,
  )

  prompt_parts.append(f"""
Story Prompt from client:
{story_prompt}
""")

  for i, character in enumerate(characters):
    prompt_parts.append(f"""
Character {i + 1}:
{character.description_xml}
""")

  if past_story_titles:
    past_stories_str = "\n\n".join(
        [f"- {title}" for title in past_story_titles])
    prompt_parts.append(f"""
Stories that you have already written:
{past_stories_str}

To improve variety and keep things fresh, please generate a story outline that is distinctly different
from these stories in terms of plot, themes, and setting.
""")

  response = _plot_llm.generate(prompt_parts, extra_log_data=extra_log_data)

  # Extract content between square brackets using regex
  match = re.search(r'\{(.*?)\}', response.text, re.DOTALL)
  if not match:
    raise ValueError(
        f"No valid JSON array found in response: {response.text}")

  response_dict = json.loads(response.text)
  chosen_plot_key = response_dict.get("chosen_plot")
  if not chosen_plot_key:
    raise ValueError(f"No chosen plot key found in response: {response.text}")

  chosen_plot_dict = response_dict.get(chosen_plot_key)
  if not chosen_plot_dict:
    raise ValueError(f"No chosen plot found in response: {response.text}")

  plot = chosen_plot_dict.get("plot")
  if not plot:
    raise ValueError(f"No plot found in response: {response.text}")

  return plot, response_dict, response.metadata


def generate_story(
    plot: str,
    user_prompt: str,
    user_guidelines: str,
    main_characters: Collection[models.Character],
    side_characters: Collection[models.Character],
    past_story_titles: Collection[str],
    learning_topic: str,
    reference_material_full_text: str,
    llm_model: llm_client.LlmModel,
    reading_level: ReadingLevel,
    extra_log_data: dict[str, Any],
) -> Generator[tuple[models.StoryData, models.GenerationMetadata], None, None]:
  """Generate a children's story using the LLM.

  Args:
      plot: The plot of the story
      user_prompt: The user's story prompt
      user_guidelines: Additional guidelines for the story
      main_characters: Collection of main characters
      side_characters: Collection of side characters
      past_story_titles: Collection of past story titles to avoid repetition
      learning_topic: Learning topic to incorporate
      reference_material_full_text: Full text of the reference material
      llm_model: The LLM model to use
      reading_level: Reading level of the story
      extra_log_data: Extra log data to include in the log
  Yields:
      Tuple of (incremental StoryData, GenerationMetadata)
  """
  story_data = models.StoryData()

  for incremental_story_data, outline_draft_metadata in _generate_outline(
      plot,
      user_prompt,
      user_guidelines,
      main_characters,
      side_characters,
      past_story_titles,
      learning_topic,
      reference_material_full_text,
      reading_level,
      llm_model,
      extra_log_data,
  ):
    story_data.update(incremental_story_data)
    yield incremental_story_data, outline_draft_metadata

  if not story_data:
    raise ValueError("No story data generated")

  for incremental_story_data, initial_draft_metadata in _generate_initial_draft(
      story_data,
      user_guidelines,
      reference_material_full_text,
      reading_level,
      llm_model,
      extra_log_data,
  ):
    yield incremental_story_data, initial_draft_metadata


def _generate_outline(
    plot: str,
    user_prompt: str,
    user_guidelines: str,
    main_characters: Collection[models.Character],
    side_characters: Collection[models.Character],
    past_story_titles: list[str],
    reference_material_topic: str,
    reference_material_full_text: str,
    reading_level: ReadingLevel,
    llm_model: llm_client.LlmModel,
    extra_log_data: dict[str, Any],
) -> Generator[tuple[models.StoryData, models.SingleGenerationMetadata], None, None]:
  """Generate an outline and initial draft of the story.

    Args:
      plot: The plot of the story
      user_prompt: The user's story prompt
      user_guidelines: Additional guidelines from the user
      main_characters: List of main character objects
      side_characters: List of side character objects
      past_story_titles: Optional list of previously generated story titles
      reference_material_topic: Topic of the reference material
      reference_material_full_text: Full text of the reference material
      reading_level: Reading level of the story
      llm_model: The LLM model to use
      extra_log_data: Extra log data to include in the log
  Yields:
      Tuple of (incremental StoryData object, generation_metadata)
  """
  prompt_parts = _get_base_prompt_parts(
      user_guidelines,
      reading_level,
  )

  prompt_parts.append(f"""
Story Prompt from client:
Version 1:
{user_prompt}
Version 2:
{plot}
""")

  main_char_desc = "\n\n".join(
      [char.description_xml for char in main_characters])
  prompt_parts.append(f"""
{"Main Characters" if len(main_characters) > 1 else "Main Character"}:
{main_char_desc}
""")

  if side_characters:
    side_char_desc = "\n\n".join(
        [char.description_xml for char in side_characters])
    prompt_parts.append(f"""
{"Side Characters" if len(side_characters) > 1 else "Side Character"}:
{side_char_desc}
""")

  if past_story_titles:
    past_stories_str = "\n\n".join(
        [f"- {title}" for title in past_story_titles])
    prompt_parts.append(f"""
Stories that you have already written:
{past_stories_str}

To improve variety and keep things fresh, please generate a story outline that is distinctly different
from these stories in terms of plot, themes, and setting.
""")

  prompt_parts.append(f"""
The story topic requested by the client is "{reference_material_topic}".

<reference_material>
{reference_material_full_text}
</reference_material>

The list of chosen concepts from the reference material should all be about the topic "{reference_material_topic}".
""")

  remaining_text = ""
  accumulated_thinking = ""
  for response in _outline_llm_by_model[llm_model].stream(
          prompt_parts, extra_log_data=extra_log_data):
    accumulated_thinking += response.thinking_text
    remaining_text += response.text_delta
    incremental_story_data, remaining_text = _parse_story_response(
        remaining_text)

    yield incremental_story_data, response.metadata

  incremental_story_data, remaining_text = _parse_story_response(remaining_text, is_final=True)
  yield incremental_story_data, models.SingleGenerationMetadata()


def _generate_initial_draft(
    story_data: models.StoryData,
    user_guidelines: str,
    reference_material_full_text: str,
    reading_level: ReadingLevel,
    llm_model: llm_client.LlmModel,
    extra_log_data: dict[str, Any],
) -> Generator[tuple[models.StoryData, models.SingleGenerationMetadata], None, None]:
  """Generate an outline and initial draft of the story.

  Args:
      user_prompt: The user's story prompt
      user_guidelines: Additional guidelines from the user
      reference_material_full_text: Full text of the reference material
      reading_level: Reading level of the story
      llm_model: The LLM model to use
      extra_log_data: Extra log data to include in the log
  Yields:
      Tuple of (incremental StoryData object, generation_metadata)
  """
  prompt_parts = _get_base_prompt_parts(
      user_guidelines,
      reading_level,
  )

  prompt_parts.append(f"""
<reference_material>
{reference_material_full_text}
</reference_material>
""")

  prompt_parts.append(story_data.outline_xml)

  prompt_parts.append(
      f"Write a funny children's story that is {_NUM_PAGES} pages long.")

  remaining_text = ""
  accumulated_thinking = ""
  for response in _initial_draft_llm_by_model[llm_model].stream(
      prompt_parts, extra_log_data=extra_log_data
  ):
    accumulated_thinking += response.thinking_text
    remaining_text += response.text_delta
    incremental_story_data, remaining_text = _parse_story_response(
        remaining_text)

    yield incremental_story_data, response.metadata

  incremental_story_data, remaining_text = _parse_story_response(remaining_text, is_final=True)
  yield incremental_story_data, models.SingleGenerationMetadata()


def _get_base_prompt_parts(
    user_guidelines: str | None,
    reading_level: ReadingLevel,
) -> list[str]:
  """Get the base parts of the prompt that are common across story generations."""
  prompt_parts = []

  # Add reading level guidelines
  reading_level_guidelines = _READING_LEVEL_GUIDELINES[reading_level]
  prompt_parts.append(f"""{reading_level_guidelines}
Make sure the plot and concepts of the story can be understood by readers at this reading level.
""")

  # Guidelines from the app
  if user_guidelines:
    prompt_parts.append(f"""
MAKE SURE to follow these guidelines:
{user_guidelines}
""")

  return prompt_parts


_OPENING_TAG_PATTERN = re.compile(r'<([a-z0-9_]+)>')
_REGEX_BY_TAG_TYPE = {
    "tone": re.compile(r'<tone>(.*?)</tone>', re.DOTALL),
    "reference": re.compile(r'<reference>(.*?)</reference>', re.DOTALL),
    "title": re.compile(r'<title>(.*?)</title>', re.DOTALL),
    "tagline": re.compile(r'<tagline>(.*?)</tagline>', re.DOTALL),
    "summary": re.compile(r'<summary>(.*?)</summary>', re.DOTALL),
    "character": re.compile(r'<character>(.*?)</character>', re.DOTALL),
    "outline": re.compile(r'<outline>(.*?)</outline>', re.DOTALL),
    "cover_illustration": re.compile(r'<cover_illustration>(.*?)</cover_illustration>', re.DOTALL),
    "page": re.compile(r'<page>(.*?)</page>', re.DOTALL),
    "plot_brainstorm": re.compile(r'<plot_brainstorm>(.*?)</plot_brainstorm>', re.DOTALL),
}

# Reference tag components
_REFERENCE_CONCEPT_REGEX = re.compile(r'<concept>(.*?)</concept>', re.DOTALL)
_REFERENCE_EXPLANATION_REGEX = re.compile(
    r'<explanation>(.*?)</explanation>', re.DOTALL)
_REFERENCE_PLOT_REGEX = re.compile(r'<plot>(.*?)</plot>', re.DOTALL)
_REFERENCE_DEMONSTRATION_REGEX = re.compile(
    r'<demonstration>(.*?)</demonstration>', re.DOTALL)

# Character tag components
_CHARACTER_NAME_REGEX = re.compile(r'<name>(.*?)</name>', re.DOTALL)
_CHARACTER_VISUAL_REGEX = re.compile(r'<visual>(.*?)</visual>', re.DOTALL)
_CHARACTER_HUMOR_REGEX = re.compile(r'<humor>(.*?)</humor>', re.DOTALL)

# Cover illustration components
_COVER_ILLUSTRATION_DESC_REGEX = re.compile(
    r'<cover_[a-z_]*illustration_[a-z_]*description>(.*?)</cover_[a-z_]*illustration_[a-z_]*description>', re.DOTALL)
_COVER_ILLUSTRATION_CHARACTER_REGEX = re.compile(
    r'<cover_[a-z_]*illustration_[a-z_]*character>(.*?)</cover_[a-z_]*illustration_[a-z_]*character>', re.DOTALL)

# Page components
_PAGE_TEXT_REGEX = re.compile(r'<text>(.*?)</text>', re.DOTALL)
_PAGE_ILLUSTRATION_DESC_REGEX = re.compile(
    r'<illustration_[a-z_]*description>(.*?)</illustration_[a-z_]*description>', re.DOTALL)
_PAGE_ILLUSTRATION_CHARACTER_REGEX = re.compile(
    r'<illustration_[a-z_]*character>(.*?)</illustration_[a-z_]*character>', re.DOTALL)
_PAGE_NUM_REGEX = re.compile(r'<num>(.*?)</num>', re.DOTALL)
_PAGE_HUMOR_REGEX = re.compile(r'<humor>(.*?)</humor>', re.DOTALL)


def _parse_story_response(
        response_text: str, is_final: bool = False) -> tuple[models.StoryData, str]:
  """Parse the LLM response text into story components.

  Args:
      response_text: Raw response text from the LLM containing story components
                 This might be a partial response with incomplete tags.
      is_final: Whether this is the final response

  Returns:
      Tuple of (StoryData object with parsed components, remaining unprocessed text)
  """
  # Initialize empty story data
  story_data = models.StoryData()
  remaining_text = _repair_xml(xml=response_text, is_final=is_final)
  prev_page_number = 0

  # Process components in the order they appear in the text
  while remaining_text:
    # Find the first opening tag
    match = _OPENING_TAG_PATTERN.search(remaining_text)
    if not match:
      # No more opening tags found
      break

    # Process based on tag type
    tag_type = match.group(1)
    tag_regex = _REGEX_BY_TAG_TYPE.get(tag_type)
    if not tag_regex:
      raise ValueError(f"Unknown tag: {tag_type}\n{remaining_text}")

    content, remaining_text = _extract_tag(
        remaining_text, tag_regex)
    if not content:
      # Did not find a complete open/close tag set, so input is likely incomplete
      break

    match tag_type:
      case "title":
        if not story_data.title:
          story_data.title = content

      case "plot_brainstorm":
        if not story_data.plot_brainstorm:
          story_data.plot_brainstorm = content

      case "tagline":
        if not story_data.tagline:
          story_data.tagline = content

      case "summary":
        if not story_data.summary:
          story_data.summary = content

      case "tone":
        if not story_data.tone:
          story_data.tone = content

      case "character":
        # Extract name, visual description, and humor from character tag
        char_name, _ = _extract_tag(content, _CHARACTER_NAME_REGEX)
        if char_name:
          visual, content = _extract_tag(
              content, _CHARACTER_VISUAL_REGEX)
          humor, content = _extract_tag(
              content, _CHARACTER_HUMOR_REGEX)
          story_data.characters[char_name] = models.StoryCharacterData(
              name=char_name, visual=visual, humor=humor
          )

      case "cover_illustration":
        description, content = _extract_tag(
            content, _COVER_ILLUSTRATION_DESC_REGEX)
        characters, content = _extract_repeated_tags(
            content, _COVER_ILLUSTRATION_CHARACTER_REGEX)

        story_data.cover_illustration = models.StoryIllustrationData(
            description=description, characters=characters
        )

      case "page":
        # Make a copy of the raw contents for debugging
        raw_page_content = content

        # Extract all components
        text, content = _extract_tag(content, _PAGE_TEXT_REGEX)
        page_num_str, content = _extract_tag(content, _PAGE_NUM_REGEX)
        if text:  # Only process page if it has text
          if page_num_str:
            page_num_int = int(page_num_str)
          else:
            page_num_int = prev_page_number + 1

          prev_page_number = page_num_int

          page_humor, content = _extract_tag(
              content, _PAGE_HUMOR_REGEX)
          illustration_desc, content = _extract_tag(
              content, _PAGE_ILLUSTRATION_DESC_REGEX)
          illustration_chars, content = _extract_repeated_tags(
              content, _PAGE_ILLUSTRATION_CHARACTER_REGEX)

          story_data.pages.append(models.StoryPageData(
              illustration=models.StoryIllustrationData(
                  description=illustration_desc,
                  characters=illustration_chars
              ),
              text=text,
              humor=page_humor,
              page_number=page_num_int,
              raw_page_content=raw_page_content,
          ))
          print(
              f"Successfully parsed page {page_num_int} with text: {text[:50]}...")
        else:
          print(
              f"Skipping page {page_num_str} due to missing text content.")

      case "reference":
        # Extract concept, explanation, plot, and demonstration from reference tag
        concept, content = _extract_tag(
            content, _REFERENCE_CONCEPT_REGEX)
        if concept:
          explanation, content = _extract_tag(
              content, _REFERENCE_EXPLANATION_REGEX)
          plot, content = _extract_tag(
              content, _REFERENCE_PLOT_REGEX)
          demonstration, content = _extract_tag(
              content, _REFERENCE_DEMONSTRATION_REGEX)

          story_data.learning_concepts[concept] = models.StoryLearningConceptData(
              explanation=explanation,
              plot=plot,
              demonstration=demonstration
          )

      case "outline":
        story_data.outline = content
        print(f"\n\n\n\n\n\nOutline:\n{content}\n\n\n\n\n\n")

      case _:
        print(f"Unexpected story tag: {tag_type}")

  return story_data, remaining_text


def _extract_tag(text: str, tag_regex: re.Pattern) -> tuple[str, str]:
  """Extract a single tag from text and return the tag contents and remaining text.

  Args:
      text: The text to search in
      tag_regex: The regex pattern to match the tag

  Returns:
      Tuple of (tag contents or empty string if not found, text with tag removed if found or original text)
  """
  if match := tag_regex.search(text):
    content = match.group(1).strip()
    # Remove the matched tag from the text
    remaining_text = text[:match.start()] + text[match.end():]
    return content, remaining_text
  return "", text


def _extract_repeated_tags(text: str, tag_regex: re.Pattern) -> tuple[list[str], str]:
  """Extract all instances of a repeating tag from text.

  Args:
      text: The text to search in
      tag_regex: The regex pattern to match the tag

  Returns:
      Tuple of (list of tag contents, text with all matching tags removed)
  """
  contents = []
  remaining_text = text

  # First find all matches without modifying the text
  matches = list(tag_regex.finditer(remaining_text))

  if not matches:
    return [], remaining_text

  # Sort matches in reverse order by start position
  # This allows us to remove matches from end to beginning,
  # preserving the positions of earlier matches
  matches.sort(key=lambda x: x.start(), reverse=True)

  # Extract content and remove tags from end to beginning
  for match in matches:
    contents.insert(0, match.group(1).strip())
    remaining_text = remaining_text[:match.start(
    )] + remaining_text[match.end():]

  return contents, remaining_text


def _repair_xml(xml: str, is_final: bool) -> str:
  """Repair the given XML string.

  Add ">" to any known tags that are missing them (e.g., "<page " or "</page ").
  If is_final is True, also repairs tags at the end (e.g., "<page") and adds
  closing tags for any known open tags that were not closed.

  Args:
      xml: The XML string to repair
      is_final: Whether this is the final response

  Returns:
      The repaired XML string
  """
  known_tags = [
      # Main document structure
      "outline", "page", "plot_brainstorm",

      # Page components
      "num", "text",

      # Story metadata
      "summary", "tagline", "title", "tone",

      # Character-related
      "character", "humor", "name", "visual",

      # Illustration-related
      "cover_illustration", "cover_illustration_character", "cover_illustration_description",
      "illustration_character", "illustration_description",

      # Reference/learning content
      "concept", "demonstration", "explanation", "plot", "reference",

      # Plot components
      "chosen_plot_idea", "client_expectations", "key_plot_points", "phase", "plot_idea"
  ]

  def add_closing_bracket(match):
    # Appends '>' to the matched incomplete tag
    return match.group(0) + ">"

  # First pass: Fix incomplete tags followed by whitespace (always)
  # and incomplete tags at the end of the string (only if is_final)
  for tag in known_tags:
    # Pattern for lookahead - what can follow an incomplete tag:
    # - Whitespace (\s)
    # - Another opening tag (<)
    # - End of string ($) if is_final=True
    lookahead_pattern = "(?=\\s|<|$)" if is_final else "(?=\\s|<)"
    incomplete_pattern = f"<(/?){tag}{lookahead_pattern}"
    xml = re.sub(incomplete_pattern, add_closing_bracket, xml)

  # Second pass: If final, add missing closing tags for known open tags
  if is_final:
    tag_stack = []
    # Use regex to find all start and end tags efficiently
    tag_matches = re.finditer(r"<(/?)([a-z0-9_-]+)>", xml)
    for match in tag_matches:
      is_closing, tag_name = match.groups()
      if tag_name in known_tags:
        if is_closing:
          if tag_stack and tag_stack[-1] == tag_name:
            tag_stack.pop()
          # else: ignore mismatched closing tags
        else:
          tag_stack.append(tag_name)

    # Add closing tags for any known tags left on the stack
    for tag in reversed(tag_stack):
      xml += f"</{tag}>"

  return xml
