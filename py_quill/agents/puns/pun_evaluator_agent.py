"""Jokes evaluator agent."""

import functools
import logging
from typing import Any, Callable, Optional

from agents import agents_common, constants
from agents.common_agents import creative_brief_agent, evaluator_agent
from google.adk.agents import BaseAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from pydantic import BaseModel, ValidationError


class PunEvaluationOutput(BaseModel):
  """Pun evaluation output."""

  text: Optional[str] = None
  pun_identification: str | None = None
  semantic_split: str | None = None

  semantic_validity_evaluation: str | None = None
  semantic_validity_passed: bool | None = None

  structural_analysis: str | None = None

  semantic_bridge_evaluation: str | None = None
  semantic_bridge_rating: str | None = None

  execution_evaluation: str | None = None
  execution_passed: bool | None = None

  final_score: int | None = None
  final_score_justification: str | None = None


def get_pun_evaluator_agent(
  input_list_fn: Optional[Callable[[Any], list[Any]]] = lambda x: x,
) -> BaseAgent:
  """Creates a multi-evaluator agent for pun evaluations."""

  all_outputs_var = constants.STATE_CRITIQUE

  return evaluator_agent.get_multi_evaluator_agent(
    name="PunEvaluator",
    description="Evaluates multiple puns.",
    num_workers=20,
    input_var=constants.STATE_ITEMS_NEW,
    output_var=all_outputs_var,
    output_type=PunEvaluationOutput,
    input_list_fn=input_list_fn,
    after_agent_callback=functools.partial(
      _set_results_to_keep_discard,
      all_outputs_var=all_outputs_var,
    ),
    instruction=
    """You are an AI analyst specializing in computational humor and linguistics. Your task is to conduct a detailed evaluation of the "punniness" of the provided text using the strict, two-phase methodology outlined below. You will first perform an objective deconstruction of the text's intended pun mechanics and then synthesize your findings into a final, justified evaluation.

Follow all steps in the specified order. Do not offer an opinion on the pun's quality until the final step.

0. Text

Output the exact text being evaluated.

## PHASE 1: LINGUISTIC DECONSTRUCTION (Objective Analysis)

Analyze the mechanics of the pun without judgment.

1. Pun Identification:

Determine whether the provided text actually is a pun. If so, state the exact word or phrase that serves as the pivot for the pun. If not, output "NOT A PUN", skip the subsequent analysis/evaluation steps, and output a 1 for the Final Rating.

2. Semantic Split:

Does the pun word/phrase have two distinct meanings in the context of the pun? If so, identify and define them clearly.

Meaning A (Contextual Meaning): Describe the meaning that fits the initial setup of the sentence (the "expected" meaning, e.g. "positive").

Meaning B (Pun Meaning): Describe the secondary meaning that is revealed to create the pun (e.g. "paw-sitive").

3. Semantic Validity Check:

Evaluate the legitimacy of both Meaning A and Meaning B. A valid pun must exploit a pre-existing ambiguity, not a fabricated one.

  * Meaning A Validity: Strictly verify if the exact phrase for Meaning A is a standard, commonly used term within the pun's specific context. Crucially, do not accept plausible-sounding compounds or justify a term's existence if it is not in common use. The term must be verifiable as pre-existing, not a wordplay-specific creation.

  * Meaning B Validity: Verify if the exact phrase for Meaning B is a valid, natural sounding pun of the exact phrase of Meaning A.

Output your evaluation of the validity of both meanings as a string. Then, output a boolean value indicating whether BOTH meanings are valid.

4. Structural Analysis:

Explain how the pun's setup primes the listener for Meaning A, and how the punchline forces a reinterpretation of the pivot phrase to reveal Meaning B.

## PHASE 2: COMEDIC SYNTHESIS (Metacognitive Judgment)

Reflect on your objective analysis from Phase 1 to make a final, reasoned judgment about the pun's quality.

5. Evaluation of the Semantic Bridge (Associative Novelty):

Reflect on the relationship between Meaning A and Meaning B by assessing its associative novelty. Is the link between the two meanings a very common, well-known cliché, or is it a more original, unexpected, or technically complex connection? A novel connection is of higher quality than a predictable one. Explain your reasoning.

Output your evaluation of the semantic bridge. Then, output the string "LOW", "MEDIUM", or "HIGH" to indicate the novelty of the connection between Meaning A and Meaning B.

6. Evaluation of Execution (Natural Language Test):

Assess the pun's integration within the sentence. To do this, test if the sentence would be grammatically correct and plausible if used in a serious, non-humorous context using only Meaning A. A high-quality execution means the sentence does not feel awkward or specifically twisted to force the pun.

Output your evaluation of the execution quality. Then, output a boolean value indicating whether the pun is well executed.

7. Final Judgment & Justification:

Based on your findings in all previous steps, provide a final numerical rating and a concise justification. Use the rating scale below, which is a direct function of your analysis.

Rating Scale:

1 - Fails: The pun fails either the Semantic Validity Check (Step 3) for Meaning A or B, OR it fails the Execution Test (Step 6). The pun is based on a non-existent concept or its delivery is ungrammatical.

2 - Groaner: Passes Validity (Step 3) and Execution (Step 6), but has Low Novelty (Step 5). The pun works, but the connection is a tired cliché.

3 - Solid: Passes Validity (Step 3) and Execution (Step 6), and has Moderate Novelty (Step 5). A clean, well-delivered pun with a standard but not cliché connection.

4 - Clever: Passes Validity (Step 3) and Execution (Step 6), and has High Novelty (Step 5). The sentence is natural, and the connection between meanings is original and witty.

5 - Genius: Passes all checks (Validity, Execution, High Novelty), plus the pun adds a deeper layer of meaning or commentary to the topic.

Final Rating: [Provide a numerical rating from 1 to 5]

Final Justification: [Provide a 1-2 sentence explanation for your rating, explicitly referencing your conclusions about the pun's semantic validity (Step 3), associative novelty (Step 5), and execution quality (Step 6).]

## PUN TO EVALUATE

{{{input_key}}}
""",
  )


def _set_results_to_keep_discard(
  callback_context: CallbackContext,
  all_outputs_var: str,
) -> None:
  """Sets the results to keep and discard."""
  final_keep_items = callback_context.state.get(constants.STATE_ITEMS_KEEP, [])
  final_discard_items = callback_context.state.get(
    constants.STATE_ITEMS_DISCARD, [])

  all_outputs = callback_context.state.get(all_outputs_var, [])

  for output in all_outputs:
    try:
      output = PunEvaluationOutput.model_validate(output)
    except ValidationError as e:
      logging.warning(
        f"Pun evaluator output is not a valid PunEvaluationOutput: {e}\n"
        f"Output: {output}")
      continue

    if pun := output.text:
      if isinstance(pun, str):
        pun = pun.strip()
      if output.final_score >= 2:
        final_keep_items.append(pun)
      elif output.final_score == 1:
        final_discard_items.append(pun)
      elif output.final_score == 0:
        # No item present
        pass

  callback_context.state[constants.STATE_ITEMS_KEEP] = final_keep_items
  callback_context.state[constants.STATE_ITEMS_DISCARD] = final_discard_items


if __name__ == "__main__":
  inputs = {
    constants.STATE_USER_INPUT:
    "Evaluate the following puns.",
    constants.STATE_ITEMS_NEW: [
      'My badminton opponent keeps making bird puns. I tell them to get a "shuttle-grip".',
      "What do you call a badminton player who can't stop telling puns? A shuttlecocky comedian!",
      'Why did the badminton player bring a broom to the match? Because he wanted to sweep the competition!',
      'A steak pun is a rare medium well done.',
      "Why did the tomato turn red? Because it saw the salad dressing!",
    ],
  }

  agent = SequentialAgent(
    name="PunEvaluatorMultiAgentPipeline",
    sub_agents=[
      creative_brief_agent.get_creative_brief_agent(),
      get_pun_evaluator_agent(),
    ],
    description="Manages the end-to-end motivational pun generation process.",
  )

  agents_common.run_agent(agent=agent, inputs=inputs)
