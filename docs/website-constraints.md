# Valor Website Constraints

This document defines the constraints for Valor's first public landing page.
The goal is to make implementation faster and keep the site aligned with the
project's OSS v1 positioning.

## Purpose

The landing page should do three things well:

1. Explain Valor in under 10 seconds.
2. Establish trust around the local-first and privacy-first model.
3. Convert interested visitors into one of:
   - GitHub repo visitors
   - local installers
   - OSS contributors

## Product Positioning

The website should consistently present Valor as:

- local-first
- privacy-first
- developer-first
- an ambient career coach for developers
- open-source local core

The page should feel like a trustworthy developer tool, not a generic AI SaaS.

## Primary Audience

The first version should optimize for:

- individual developers who already use coding assistants
- privacy-conscious developers who are skeptical of hosted career tooling
- early OSS users and contributors

It should not try to speak equally to:

- managers buying software for teams
- HR buyers
- broad consumer productivity audiences

## Messaging Constraints

The page must make these points clear:

- Valor works through assistant-driven developer workflows.
- Valor captures work that does not show up in commits alone.
- Valor stores its local core data on the user's machine.
- This OSS repo does not include built-in telemetry, cloud sync, or a hosted backend.
- External integrations depend on the host assistant and user environment.

The page must avoid:

- promising promotions or career outcomes
- implying fully offline or air-gapped operation by default
- implying employer surveillance or manager oversight features
- sounding like HR software
- vague "AI that transforms your career" marketing language

## Trust Constraints

Trust should be a first-class section, not a footnote.

The landing page should explicitly surface:

- local storage by default
- inspectable prompts and logic
- no built-in telemetry in this repo
- clear trust-boundary caveat around hosted assistants and integrations

The page should link clearly to:

- `README.md`
- `PRIVACY.md`
- `SECURITY.md`
- the GitHub repository

## Content Constraints

The first version should stay compact. Recommended sections:

1. Hero
2. Why Valor exists
3. How it works
4. What exists today
5. Privacy and trust boundary
6. Open-source / local-core positioning
7. Final CTA

Nice-to-have sections, but not required for v1:

- screenshots
- animation-heavy product demo
- FAQ
- contributor spotlight
- blog/news feed

## Hero Constraints

The hero should communicate:

- what Valor is
- who it is for
- why it is different

The hero should not lead with:

- abstract philosophy
- a long founder story
- roadmap details
- too many CTAs

Preferred CTA structure:

- primary: `View on GitHub`
- secondary: `Read the README` or `How it works`

If we add install guidance to the page, it should be below the hero rather than
competing with it.

## Visual Constraints

The site should feel modern, deliberate, and technical.

Desired qualities:

- calm, high-trust, and sharp
- strong typography
- restrained but intentional motion
- a visual language that suggests local tools, files, systems, and workflows

Avoid:

- generic AI gradients everywhere
- glossy enterprise SaaS aesthetics
- purple-glow default AI branding
- excessive glassmorphism
- overstuffed dashboards on the landing page

The design should feel closer to:

- a premium developer tool
- a thoughtful open-source project

Than to:

- a growth-marketing startup template
- a crypto landing page
- a generic "AI copilot" site

## UX Constraints

The first version should be:

- single-page
- mobile-friendly
- fast-loading
- accessible
- easy to scan

It should work without:

- account creation
- user auth
- forms
- cookies banners caused by analytics or tracking scripts

## Technical Constraints

Because this repo is primarily the OSS core, the website should be isolated.

Constraints:

- keep website code in a dedicated `website/` or `site/` directory
- do not mix website dependencies into the Python runtime setup
- prefer a static site with minimal build complexity
- no backend required for v1
- no analytics scripts for v1 unless explicitly added later

The website should be deployable to a subdomain on a personal domain as a
static build.

## Repo Constraints

The website should support the OSS repo, not overshadow it.

That means:

- GitHub remains the source of truth for code and installation
- the site should link back into the repo, not duplicate the entire docs set
- README and website messaging should stay consistent
- product claims on the site must remain true to the shipped open-source core

## Copy Constraints

Tone should be:

- clear
- confident
- developer-native
- privacy-literate

Tone should not be:

- hypey
- corporate
- over-explained
- emotionally manipulative

## v1 Success Criteria

The first landing page is successful if a new visitor can quickly understand:

- what Valor is
- why it is different
- whether they trust the model
- where to go next

For v1, that is enough.
