# Sensor Interface Node — Software Requirements Specification

<!-- Fully synthetic document for the maluS demo. No real product or data. -->

## 1. Introduction

This document specifies the software requirements for the Sensor Interface Node
(SIN), a fictional data-acquisition controller used only to demonstrate maluS.

## 2. Scope

The SIN reads analog sensors and streams measurements to a host computer.

## 3. Definitions

The operator is the person who configures the node. A measurement is one sampled
value with its timestamp.

## 4. Sampling

The acquisition timeout shall be configurable by the operator. {COMM|type=technical|sev=major: the acquisition timeout is not bounded}

## 5. Storage

All measurements are written to disk in CSV format. {SUGG: "disk" -> "the device"}

## 6. Interfaces

The node exposes a serial interface at 115200 baud.

## 7. Timing

Samples shall be timestamped with millisecond resolution.

## 8. Error handling

On sensor failure, the node shall log an error and continue operating.

## 9. Security

Configuration changes require operator authentication.

## 10. Acceptance

The node passes acceptance when every requirement has been verified by a reviewer.
