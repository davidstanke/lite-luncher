---
trigger: always_on
description: Do not allow silent mock/simulated travel data fallbacks
---

When implementing or editing tools that interface with travel APIs (e.g. Directions, Places, Hotels, Activities):

1. **Never Return Mock/Simulated Data**: Do not return pre-defined mock datasets or dynamic LLM-generated mock routes/places when an API key is missing, is a placeholder (`YOUR_MAPS_API_KEY`), or when a live API call fails.
2. **Raise Fatal TravelAPIError**: Always raise a descriptive, fatal `TravelAPIError` with highly structured, multi-line diagnostic blocks detailing:
   - **Failed Tool**: The name of the failed function.
   - **Arguments**: The exact arguments provided to the tool.
   - **API Key State**: The status of `GOOGLE_MAPS_API_KEY` (e.g. `MISSING`, `Placeholder`, or `PRESENT but failing`).
   - **Raw Error**: The raw exception message or HTTP code (e.g., `HTTP Error 403: Forbidden` or `SSL: CERTIFICATE_VERIFY_FAILED`).
   - **Actionable Steps**: Precise troubleshooting instructions for developers.
3. **Handle macOS SSL Certificate Failures**: Explicitly check for `CERTIFICATE_VERIFY_FAILED` in urllib/network calls, and instruct engineers to run:
   `/Applications/Python\ <version>/Install\ Certificates.command`
   to install the system certificate authorities for their active Python environment.
4. **Places API (New)**: For Places v1 textSearch endpoints (`https://places.googleapis.com/v1/...`), verify that the modern **"Places API (New)"** is explicitly enabled in the Google Cloud Console (legacy "Places API" will cause an HTTP 403 Forbidden).
