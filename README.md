# Hear Your Heart 

> Cardiac health, explained for you.

Built at VenusHacks 2026 — Track 3: Heart Health at Warp Speed
Sponsored by the California Office of the Surgeon General

## The Problem

Heart disease is the #1 killer of women in California. Pregnant and postpartum women are the most vulnerable and the least likely to receive proper cardiac screening. When they do receive a diagnosis, medical terminology creates a gap between what the doctor said and what the patient understood. That gap costs lives.

$60 billion is spent annually on maternal and newborn care in the United States. A significant portion comes from complications we could have caught earlier.

## What We Built

Hear Your Heart is a wearable-powered maternal cardiac health companion that helps pregnant and postpartum women understand their heart health — in plain English, designed for them.

Three entry points, one destination:

- **Apple Watch ECG** — upload your ECG export and analyze your cardiac rhythm
- **Doctor's Note** — photograph your handwritten note and we'll translate it for you
- **Risk Profile** — enter your maternal health factors and get a personalized cardiac risk assessment

All three paths lead to an immersive 3D heart visualization that illuminates exactly what's happening in your specific heart — with plain language explanations, doctor questions, and a script for what to say at your next appointment.

## Features

- Immersive 3D anatomical heart visualization with interactive region exploration
- Particle landing animation and emotional adaptive interface
- Pregnancy onboarding — prenatal and postpartum modes
- Maternal cardiac risk factor form with 8 prenatal inputs and 5 postpartum clinical flags
- Apple Watch ECG upload flow
- Doctor's note OCR upload with plain language translation
- Personalized patient profile with photo, medications, allergies, and doctor visit notes
- Risk tier output — Low, Medium, High — with contributing factors and recommended next steps
- Doctor script — exactly what to say at your next appointment
- Interactive heart region labels with pregnancy-specific definitions and doctor questions

## Tech Stack

- React + TypeScript + Vite
- Three.js + React Three Fiber + Drei
- Framer Motion
- Tailwind CSS
- FastAPI (Python)
- scikit-learn (XGBoost + Logistic Regression)
- California Department of Public Health maternal health data
- CDC WONDER maternal mortality data

## Research Foundation

- Virtual and Augmented Reality in Cardiac Surgery — Brazilian Journal of Cardiovascular Surgery 2022
- Real-time Visualization of Retrograde Cardioplegia Delivery — Harvard/Brigham and Women's Hospital 2008
- The Reliability of the Apple Watch ECG — Cureus 2023
- MVKT-ECG: Efficient single-lead ECG classification — Tsinghua University, Computers in Biology and Medicine 2023

## The Science

Risk factors tracked: advanced maternal age, hypertension, diabetes, obesity, prior adverse pregnancy history, smoking, multiple gestation.

Prenatal model: Logistic Regression / XGBoost trained on California maternal health data — 8 minimum inputs, outputs calibrated probability and risk tier.

Postpartum engine: Transparent rule-based profile using 5 delivery outcome flags — no black box ML, fully explainable to patients and providers.

Fairness audit: Performance evaluated across race, ethnicity, insurance status, and age group. Race and ethnicity are never used as model inputs per HHS Section 1557.

## Team

My Truong · Mary Nguyen · Harry Tran · Ben Nguyen

VenusHacks 2026 — University of California, Irvine
