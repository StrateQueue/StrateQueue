# [Platform A] ↔ [Platform B] Cross-Reference

This document provides a comprehensive mapping between [Platform A Name](link) and [Platform B Name](link) to help developers translate concepts, orders, and workflows between [use case description].

**Legend:**
- `platA` = Platform A (version/type)
- `platB` = Platform B (version/type)
- `→` = same concept / direct translation
- `≈` = closest practical analogue (behavior differs, see notes)
- `✗` = not supported / no equivalent

---

## 1. Order Creation & Types

| Concept                    | Platform A API                                  | Platform B API                               |
|----------------------------|------------------------------------------------|-----------------------------------------------|
| **Order Side**             |                                                |                                               |
| Long position              | `example syntax`                               | `example syntax`                              |
| Short position             | `example syntax`                               | `example syntax`                              |
| **Basic Order Types**      |                                                |                                               |
| Market order               | `example`                                      | `example`                                     |
| Limit order                | `example`                                      | `example`                                     |
| Stop-market order          | `example`                                      | `example`                                     |
| Stop-limit order           | `example`                                      | `example`                                     |
| **Advanced Order Types**   |                                                |                                               |
| [Advanced type 1]          | `example`                                      | `example or ≈ alternative`                   |
| [Advanced type 2]          | `example`                                      | `example or ≈ alternative`                   |

### Code Examples - Order Creation

```language
# ═══════════════════════════════════════════════════════════════════════════
# [Common use case example 1]
# ═══════════════════════════════════════════════════════════════════════════
# Platform A
[code example]

# Platform B  
[code example]

# ═══════════════════════════════════════════════════════════════════════════
# [Common use case example 2]
# ═══════════════════════════════════════════════════════════════════════════
# Platform A
[code example]

# Platform B
[code example]
```

---

## 2. Order Parameters & Sizing

| Parameter                  | Platform A                                     | Platform B                                   |
|----------------------------|------------------------------------------------|----------------------------------------------|
| **Quantity/Sizing**        |                                                |                                              |
| [Size type 1]              | `example`                                      | `example`                                    |
| [Size type 2]              | `example`                                      | `example or ≈ alternative`                  |
| **Pricing**                |                                                |                                              |
| [Price type 1]             | `example`                                      | `example`                                    |
| [Price type 2]             | `example`                                      | `example`                                    |
| **Order Management**       |                                                |                                              |
| [Management feature 1]     | `example`                                      | `example or ✗`                               |
| [Management feature 2]     | `example`                                      | `example or ✗`                               |

---

## 3. Order Status & Lifecycle Management

| Action/Status              | Platform A API                                | Platform B API                               |
|----------------------------|------------------------------------------------|----------------------------------------------|
| **Order States**           |                                                |                                              |
| [State 1]                  | `status example`                               | `equivalent or ≈`                            |
| [State 2]                  | `status example`                               | `equivalent or ≈`                            |
| **Order Management**       |                                                |                                              |
| [Action 1]                 | `API call example`                             | `equivalent call`                            |
| [Action 2]                 | `API call example`                             | `equivalent call`                            |

### Code Examples - Order Management

```language
# ═══════════════════════════════════════════════════════════════════════════
# [Common management task 1]
# ═══════════════════════════════════════════════════════════════════════════
# Platform A
[code example]

# Platform B
[code example]

# ═══════════════════════════════════════════════════════════════════════════
# [Common management task 2]  
# ═══════════════════════════════════════════════════════════════════════════
# Platform A
[code example]

# Platform B
[code example]
```

---

## 4. Position & Account Information

| Information                | Platform A API                                | Platform B API                               |
|----------------------------|------------------------------------------------|----------------------------------------------|
| **Account Data**           |                                                |                                              |
| [Account info type 1]      | `API call`                                     | `equivalent call`                            |
| [Account info type 2]      | `API call`                                     | `equivalent call or ✗`                      |
| **Position Data**          |                                                |                                              |
| [Position info type 1]     | `API call`                                     | `equivalent call`                            |
| [Position info type 2]     | `API call`                                     | `equivalent call`                            |
| **Trade History**          |                                                |                                              |
| [History type 1]           | `API call`                                     | `equivalent call`                            |
| [History type 2]           | `API call`                                     | `equivalent call`                            |

### Code Examples - Positions

```language
# ═══════════════════════════════════════════════════════════════════════════
# [Common position task 1]
# ═══════════════════════════════════════════════════════════════════════════
# Platform A
[code example]

# Platform B
[code example]

# ═══════════════════════════════════════════════════════════════════════════
# [Common position task 2]
# ═══════════════════════════════════════════════════════════════════════════
# Platform A
[code example]

# Platform B
[code example]
```

---

## 5. Event Handling & Streaming

| Event Type                 | Platform A                                     | Platform B                                   |
|----------------------------|------------------------------------------------|----------------------------------------------|
| **Real-time Updates**      |                                                |                                              |
| [Event type 1]             | `streaming API example`                        | `equivalent or ≈`                            |
| [Event type 2]             | `streaming API example`                        | `equivalent or ≈`                            |
| **Callback Methods**       |                                                |                                              |
| [Callback type 1]          | `callback example`                             | `equivalent callback`                        |
| [Callback type 2]          | `callback example`                             | `equivalent callback`                        |

---

## 6. Key Differences & Limitations

### Features Available in Platform A but NOT in Platform B

| Feature                    | Platform A                                     | Platform B Alternative                       |
|----------------------------|------------------------------------------------|----------------------------------------------|
| **[Feature category 1]**   | [Description]                                  | [Alternative or ✗]                           |
| **[Feature category 2]**   | [Description]                                  | [Alternative or ✗]                           |

### Features Available in Platform B but NOT in Platform A

| Feature                    | Platform B                                     | Platform A Alternative                       |
|----------------------------|------------------------------------------------|----------------------------------------------|
| **[Feature category 1]**   | [Description]                                  | [Alternative or ✗]                           |
| **[Feature category 2]**   | [Description]                                  | [Alternative or ✗]                           |

---

## 7. Migration Checklist

### From Platform A to Platform B

- [ ] **[Migration step 1]**: [Description of what needs to change]
- [ ] **[Migration step 2]**: [Description of what needs to change]
- [ ] **[Migration step 3]**: [Description of what needs to change]
- [ ] **[Migration step 4]**: [Description of what needs to change]
- [ ] **[Migration step 5]**: [Description of what needs to change]

### From Platform B to Platform A

- [ ] **[Migration step 1]**: [Description of what needs to change]
- [ ] **[Migration step 2]**: [Description of what needs to change]
- [ ] **[Migration step 3]**: [Description of what needs to change]
- [ ] **[Migration step 4]**: [Description of what needs to change]
- [ ] **[Migration step 5]**: [Description of what needs to change]

---

## 8. Common Patterns & Examples

### Pattern: [Common Use Case 1]

```language
# ═══════════════════════════════════════════════════════════════════════════
# Platform A - [Description]
# ═══════════════════════════════════════════════════════════════════════════
[detailed code example]

# ═══════════════════════════════════════════════════════════════════════════  
# Platform B - [Description] 
# ═══════════════════════════════════════════════════════════════════════════
[detailed code example]
```

### Pattern: [Common Use Case 2]

```language
# ═══════════════════════════════════════════════════════════════════════════
# Platform A - [Description]
# ═══════════════════════════════════════════════════════════════════════════
[detailed code example]

# ═══════════════════════════════════════════════════════════════════════════
# Platform B - [Description]
# ═══════════════════════════════════════════════════════════════════════════
[detailed code example]
```

---

## References

- **Platform A Documentation**: [link]
- **Platform A API Reference**: [link]
- **Platform B Documentation**: [link]  
- **Platform B API Reference**: [link]

---

## Notes

[Any additional notes, caveats, or important considerations for this specific mapping] 