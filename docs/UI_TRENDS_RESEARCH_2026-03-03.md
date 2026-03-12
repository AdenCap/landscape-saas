# UI/UX Trend Research — FieldLgx (2026-03-03)

## Sources sampled
- Web trend roundups (B2B SaaS and dashboard UX)
- Reddit SaaS conversion feedback threads
- Enterprise UX guidance emphasizing progressive disclosure

## Key findings to apply

1. **Clear value in first viewport**
   - Users decide quickly if product is relevant; hero must state outcome plainly.

2. **Motion should support understanding**
   - Subtle transitions/reveals increase perceived quality when restrained.
   - Heavy motion harms speed and trust.

3. **Progressive disclosure wins in SaaS dashboards**
   - Show critical metrics first, details on interaction.

4. **Mobile conversion is non-negotiable**
   - Community feedback repeatedly flags mobile readability/CTA issues as conversion killers.

5. **Comparison + proof improves trust**
   - “How we compare” and social/operational proof sections consistently cited as helpful.

6. **Predictable pricing messaging is a differentiator**
   - Transparent pricing and low surprise costs reduce buyer hesitation.

## Recommended design direction for FieldLgx

- Keep premium visual tone (strong hierarchy, clean spacing, subtle depth)
- Lean into operator outcomes (time saved, faster collections, clearer dispatch)
- Use restrained motion across landing + app surfaces
- Standardize a token system and component consistency
- Maintain speed/accessibility guardrails

## Immediate implementation priorities

1. Finalize a reusable design token layer across templates
2. Add motion primitives with reduced-motion fallback
3. Unify component styling (tabs, cards, tables, forms)
4. Improve mobile CTA and table ergonomics across core flows
5. Add stronger proof/comparison section on landing
