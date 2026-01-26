# AI Controller Integration Plan

## Problem
The AI Async Controller exists but is not connected to the ingestion pipeline. The main trading loop bypasses it entirely, going directly from ingestion queue to strategy evaluation.

## Current Flow
Scanner → Ingestion Pipeline → Decision Queue → Main Trading Loop (Strategy → Entry → Position → Risk → Execute)

## Target Flow
Scanner → Ingestion Pipeline → Decision Queue → AI Controller → Opportunity Queue → Main Trading Loop

## Implementation Steps

### 1. Modify EliteAsyncAIController
- [ ] Add consumption logic to read from decision queue
- [ ] Add token deduplication by chain + address
- [ ] Add promotion logic to create TradeOpportunity objects
- [ ] Add opportunity queue to output processed opportunities
- [ ] Add lifecycle management for background tasks

### 2. Update main.py
- [ ] Initialize AI controller in composition
- [ ] Connect AI controller to decision queue and create opportunity queue
- [ ] Start AI controller background tasks
- [ ] Update trading loop to consume from opportunity queue

### 3. Update Trading Loop
- [ ] Change from consuming TokenCandidate to TradeOpportunity
- [ ] Remove token-to-opportunity conversion logic (now handled by AI controller)

### 4. Testing
- [ ] Verify tokens flow through AI controller
- [ ] Verify deduplication works
- [ ] Verify opportunities are created and consumed
- [ ] Verify trading loop still functions
