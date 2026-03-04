"""
Fill planner for label-driven form filling.

Takes detected form fields + user profile and produces a structured fill plan
with confidence scoring. Separates rule-matched fields from AI-required fields
and supports batch AI resolution for cost optimization.

Usage:
    planner = FillPlanner(profile, ai_responder)
    plan = planner.build_plan(fields)
    planner.resolve_ai_fields(plan)
    # plan.actions now all have intended_value set
"""

import json
import re
from dataclasses import dataclass, field as dc_field
from typing import List, Optional, Dict

from longform.label_normalizer import get_canonical_key


@dataclass
class FillAction:
    """A planned action for filling a single form field."""
    field: object = None           # FormField reference
    field_index: int = 0           # Position in page field list
    intended_value: str = ""       # What to fill
    source: str = ""               # "profile", "rule", "ai", "batch_ai", "skip"
    confidence: float = 0.0        # 0.0 to 1.0
    needs_ai: bool = False         # True if AI call required
    question_text: str = ""        # The label/question for AI batching
    max_length: int = 0            # Character limit (0 = unlimited)
    skip_reason: str = ""          # If source="skip", why


@dataclass
class FillPlan:
    """Complete fill plan for a page of form fields."""
    actions: List[FillAction] = dc_field(default_factory=list)
    ai_needed_count: int = 0
    rule_matched_count: int = 0
    skip_count: int = 0
    page_url: str = ""

    def to_schema_dict(self):
        """Export as auditable JSON schema for logging."""
        return {
            "total_fields": len(self.actions),
            "ai_needed": self.ai_needed_count,
            "rule_matched": self.rule_matched_count,
            "skipped": self.skip_count,
            "fields": [
                {
                    "label": a.field.label if a.field else "",
                    "type": a.field.field_type if a.field else "",
                    "source": a.source,
                    "confidence": round(a.confidence, 2),
                    "intended_value": (a.intended_value or "")[:80],
                    "needs_ai": a.needs_ai,
                    "skip_reason": a.skip_reason,
                }
                for a in self.actions
            ],
        }

    def summary(self):
        """One-line summary string for logging."""
        return (
            f"FillPlan: {len(self.actions)} fields "
            f"({self.rule_matched_count} rule, "
            f"{self.ai_needed_count} AI, "
            f"{self.skip_count} skip)"
        )


class FillPlanner:
    """Builds structured fill plans for form pages.

    Separates rule-matched fields (instant, free) from AI-required fields
    (batched or individual API calls).
    """

    def __init__(self, profile, ai_responder):
        """
        Args:
            profile: MasterProfile instance
            ai_responder: AIResponder instance (for rule-based checks and AI calls)
        """
        self.profile = profile
        self.ai = ai_responder

    def build_plan(self, fields, page_url=""):
        """Build a fill plan for all detected fields.

        Step 1: For each field, try rule-based matching first
        Step 2: Mark unresolved fields as needs_ai=True
        Step 3: Return plan with confidence scores

        Args:
            fields: List of FormField objects from FieldDetector
            page_url: Current page URL for logging

        Returns:
            FillPlan with actions for each field
        """
        plan = FillPlan(page_url=page_url)

        for i, field in enumerate(fields):
            action = self._plan_single_field(field, i)
            plan.actions.append(action)

            if action.source == "skip":
                plan.skip_count += 1
            elif action.needs_ai:
                plan.ai_needed_count += 1
            else:
                plan.rule_matched_count += 1

        return plan

    def _plan_single_field(self, field, index):
        """Plan how to fill a single field.

        Priority:
        1. Skip already-filled, password, and hidden fields
        2. File uploads handled separately
        3. Try rule-based match (personal data, salary, work rights, etc.)
        4. Mark as needs_ai for later resolution
        """
        action = FillAction(
            field=field,
            field_index=index,
            max_length=field.max_length if hasattr(field, 'max_length') else 0,
        )

        # Skip already-filled fields (except radio/checkbox which need selection)
        if (hasattr(field, 'current_value') and field.current_value
                and field.field_type not in ("radio", "checkbox")):
            action.source = "skip"
            action.skip_reason = "already_filled"
            action.confidence = 1.0
            return action

        # Skip password fields (never auto-fill)
        if field.field_type == "password":
            action.source = "skip"
            action.skip_reason = "never_autofill_password"
            return action

        # Skip hidden/honeypot fields
        if field.field_type == "hidden":
            action.source = "skip"
            action.skip_reason = "hidden_field"
            return action

        # File uploads handled separately by document_manager
        if field.field_type == "file":
            action.source = "skip"
            action.skip_reason = "handled_by_doc_manager"
            return action

        # Get the label to match against
        label = field.label or ""
        if not label and hasattr(field, 'placeholder'):
            label = field.placeholder or ""
        if not label and hasattr(field, 'name'):
            label = field.name or ""

        action.question_text = label

        # --- Try rule-based matching ---

        # Text-like fields: text, email, tel, number, url, date, textarea
        if field.field_type in ("text", "email", "tel", "number", "url", "date", "textarea"):
            rule_value = self.ai._try_rule_based(label)
            if rule_value is not None and rule_value != "":
                action.intended_value = str(rule_value)
                action.source = "profile"
                action.confidence = 0.95
                return action

            # Needs AI
            action.needs_ai = True
            action.source = "ai"
            return action

        # Select dropdowns
        if field.field_type == "select":
            options = field.options if hasattr(field, 'options') else []
            if options and label:
                rule_value = self.ai._rule_based_dropdown(
                    label.lower(), options
                )
                if rule_value:
                    action.intended_value = rule_value
                    action.source = "rule"
                    action.confidence = 0.9
                    return action

            action.needs_ai = True
            action.source = "ai"
            return action

        # Radio buttons
        if field.field_type == "radio":
            options = field.options if hasattr(field, 'options') else []
            if options and label:
                rule_value = self.ai._rule_based_radio(
                    label.lower(), options
                )
                if rule_value:
                    action.intended_value = rule_value
                    action.source = "rule"
                    action.confidence = 0.9
                    return action

            action.needs_ai = True
            action.source = "ai"
            return action

        # Checkboxes — always need AI (multi-select logic)
        if field.field_type == "checkbox":
            action.needs_ai = True
            action.source = "ai"
            return action

        # Unknown field type — try rule-based, fallback to AI
        rule_value = self.ai._try_rule_based(label)
        if rule_value is not None and rule_value != "":
            action.intended_value = str(rule_value)
            action.source = "profile"
            action.confidence = 0.8
            return action

        action.needs_ai = True
        action.source = "ai"
        return action

    # ===========================================
    # AI Resolution
    # ===========================================

    def resolve_ai_fields(self, plan):
        """Resolve all needs_ai fields via batch AI call or individual calls.

        Args:
            plan: FillPlan with some actions marked needs_ai=True
        """
        ai_actions = [a for a in plan.actions if a.needs_ai]
        if not ai_actions:
            return

        print(f"    [FillPlan] Resolving {len(ai_actions)} AI fields...")

        # Try batch first if we have multiple questions
        if len(ai_actions) >= 2:
            batch_ok = self._resolve_batch(ai_actions)
            if batch_ok:
                # Check if all were resolved
                remaining = [a for a in ai_actions if a.needs_ai]
                if not remaining:
                    return
                ai_actions = remaining

        # Fallback: individual calls for remaining fields
        for action in ai_actions:
            if action.needs_ai:
                self._resolve_individual(action)

    def _resolve_batch(self, actions):
        """Attempt to resolve all AI fields in one call.

        Returns True if at least some answers were resolved.
        """
        try:
            # Build questions list for batch
            questions = []
            for action in actions:
                q = {
                    "index": action.field_index,
                    "label": action.question_text,
                    "type": action.field.field_type if action.field else "text",
                    "max_length": action.max_length,
                }
                if hasattr(action.field, 'options') and action.field.options:
                    q["options"] = action.field.options
                questions.append(q)

            # Call batch method on ai_responder
            if hasattr(self.ai, 'answer_batch'):
                answers = self.ai.answer_batch(questions)
            else:
                return False

            if not answers:
                return False

            resolved = 0
            for action in actions:
                idx_key = str(action.field_index)
                answer = answers.get(idx_key) or answers.get(action.field_index)
                if answer:
                    action.intended_value = str(answer)
                    action.confidence = 0.7
                    action.needs_ai = False
                    action.source = "batch_ai"
                    resolved += 1

            print(f"    [FillPlan] Batch resolved {resolved}/{len(actions)} fields")
            return resolved > 0

        except Exception as e:
            print(f"    [FillPlan] Batch AI failed ({e}), using individual calls")
            return False

    def _resolve_individual(self, action):
        """Resolve a single AI field via individual API call."""
        field = action.field
        label = action.question_text

        try:
            if field.field_type in ("text", "email", "tel", "number",
                                     "url", "date", "textarea"):
                max_len = action.max_length if action.max_length else None
                answer = self.ai.answer_text_question(label, max_len)
                if answer:
                    action.intended_value = answer
                    action.confidence = 0.7
                    action.needs_ai = False

            elif field.field_type == "select":
                options = field.options if hasattr(field, 'options') else []
                if options:
                    answer = self.ai.select_dropdown_option(label, options)
                    if answer:
                        action.intended_value = answer
                        action.confidence = 0.7
                        action.needs_ai = False

            elif field.field_type == "radio":
                options = field.options if hasattr(field, 'options') else []
                if options:
                    answer = self.ai.select_radio_option(label, options)
                    if answer:
                        action.intended_value = answer
                        action.confidence = 0.7
                        action.needs_ai = False

            elif field.field_type == "checkbox":
                options = field.options if hasattr(field, 'options') else []
                if options:
                    answers = self.ai.select_checkbox_options(label, options)
                    if answers:
                        action.intended_value = json.dumps(answers)
                        action.confidence = 0.7
                        action.needs_ai = False

        except Exception as e:
            print(f"    [FillPlan] Individual AI failed for '{label}': {e}")
            action.confidence = 0.0
