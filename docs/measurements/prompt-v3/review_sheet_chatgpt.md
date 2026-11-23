# Prompt v3 experiment: blind review sheet

Label each reply as Riley's next turn: `y` if it is an acceptable next turn, `n` if not, by your own judgment.

- Model and prompt are hidden. Several items share a conversation.
- Please label every item before opening anything in `holdout-private/prompt-v3/` or seeing any score or suggested label.
- A reason is optional. Note below whether you used an AI assistant.

Used an AI assistant while labelling (yes/no): yes

Reviewer attribution: ChatGPT supplied all 96 decisions and reasons using the requester’s summary of feedback from two students preparing to become doctors. The students gave feedback on sample interviews. These entries are AI-generated judgments.

---

## R01

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen. They didn't order it until the next shift, and by then he had gone into septic shock and was moved to the ICU.

Riley's proposed next turn:

> That sounds like a difficult situation, and you were clearly trying to escalate a real concern. What did you do to advocate for the patient after your initial pages weren’t acted on?

Accept R01? (y/n): y

Reason (optional): The applicant already described the ICU transfer. Asking what they tried after the unanswered pages explores a distinct advocacy decision.

---

## R02

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly. After that she stayed calm for the rest of his stay, and she thanked the pharmacist on her way out.

Riley's proposed next turn:

> It sounds like you took time to explain the schedule and bring in the pharmacist, which helped ease her concerns. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R02? (y/n): y

Reason (optional): The wife’s reaction settles the outcome. Riley acknowledges the explanation and pharmacist call, then moves to advocacy.

---

## R03

Conversation so far:

> **Riley:** That's all my questions. What questions do you have for me about the position?
>
> **Applicant:** I've done three years on a step-down unit but never ICU. What would orientation look like for me?

Riley's proposed next turn:

> With your three years of acute care experience on step-down, you would complete a 12-week orientation paired with a dedicated preceptor to help you transition to the ICU. Is there anything else you'd like to know about the role?

Accept R03? (y/n): y

Reason (optional): It answers the applicant’s question with the 12 weeks and dedicated preceptor and leaves room for another question.

---

## R04

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen.

Riley's proposed next turn:

> That was a great catch advocating for your patient. What was the outcome after the resident ran those tests?

Accept R04? (y/n): n

Reason (optional): The applicant requested the tests. “After the resident ran those tests” assumes the request was acted on and “great catch” endorses a conclusion before hearing the outcome.

---

## R05

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly.

Riley's proposed next turn:

> What was the outcome after that conversation?

Accept R05? (y/n): y

Reason (optional): The applicant described what they did. One short question gives them room to say how it turned out.

---

## R06

Conversation so far:

> **Riley:** Hi Morgan, this is Riley, a virtual recruiting assistant with Acme Health, calling about the Medical ICU nurse position you applied for. Is now a good time to talk?
>
> **Applicant:** Yeah, I'm on my break, so I have a few minutes.

Riley's proposed next turn:

> Thanks, and just so you know, this call is recorded and shared with our recruiting team. May I continue?

Accept R06? (y/n): y

Reason (optional): Riley discloses recording and sharing, asks permission, and gives Morgan the next turn.

---

## R07

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly.

Riley's proposed next turn:

> You helped address her frustration by explaining the schedule and bringing in the pharmacist. How was the situation resolved after that?

Accept R07? (y/n): y

Reason (optional): It connects the follow-up to the medication schedule and pharmacist and asks for the missing resolution.

---

## R08

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen.

Riley's proposed next turn:

> You noticed the change early and pushed for a broader workup instead of assuming it was just pain. What happened after the sepsis screen and lactate were done?

Accept R08? (y/n): n

Reason (optional): “After the sepsis screen and lactate were done” turns a request for tests into a completed workup. An outcome question makes sense, but its premise is unsupported.

---

## R09

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly. After that she stayed calm for the rest of his stay, and she thanked the pharmacist on her way out.

Riley's proposed next turn:

> That sounds like you addressed the concern directly and helped her get answers from the pharmacist. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R09? (y/n): y

Reason (optional): The wife stayed calm and thanked the pharmacist. Riley recognizes how the applicant helped and moves on.

---

## R10

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening. Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it.

Riley's proposed next turn:

> Thank you for walking me through that. Now, describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R10? (y/n): y

Reason (optional): The applicant explicitly says the complaint remained unresolved. A brief transition to advocacy is appropriate.

---

## R11

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen. They didn't order it until the next shift, and by then he had gone into septic shock and was moved to the ICU.

Riley's proposed next turn:

> Thank you for sharing that. Would you like to ask me any questions about the role or the unit?

Accept R11? (y/n): y

Reason (optional): The applicant has given the escalation, delay, and outcome. Inviting questions is a reasonable close to the behavioral section, though the acknowledgment is generic.

---

## R12

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening. Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it.

Riley's proposed next turn:

> Thank you for sharing that experience, even if the outcome wasn't as smooth as you had hoped. For the next question, could you describe a time you advocated for a patient whose needs weren't immediately recognized?

Accept R12? (y/n): y

Reason (optional): Riley accepts the difficult outcome and moves on without asking the applicant to supply a resolution they never saw.

---

## R13

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly. After that she stayed calm for the rest of his stay, and she thanked the pharmacist on her way out.

Riley's proposed next turn:

> Thank you, that sounds like you addressed her concern directly and helped her get clearer information. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R13? (y/n): y

Reason (optional): It acknowledges how the applicant addressed the wife’s concerns and moves to the next behavioral question.

---

## R14

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly.

Riley's proposed next turn:

> What was the outcome after that conversation?

Accept R14? (y/n): y

Reason (optional): It asks for the outcome the applicant has yet to give and leaves the answer open.

---

## R15

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening.

Riley's proposed next turn:

> What happened after you offered the video call?

Accept R15? (y/n): y

Reason (optional): It asks what happened after the offer and leaves open whether the video call took place.

---

## R16

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly.

Riley's proposed next turn:

> You helped by explaining the schedule and connecting her directly with the pharmacist. What happened after that?

Accept R16? (y/n): y

Reason (optional): It names the two actions the applicant actually took and asks what happened next.

---

## R17

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening. Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it.

Riley's proposed next turn:

> Thanks for being honest about that. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R17? (y/n): y

Reason (optional): The applicant was candid about the unresolved complaint. Riley acknowledges that and advances.

---

## R18

Conversation so far:

> **Riley:** That's all my questions. What questions do you have for me about the position?
>
> **Applicant:** I've done three years on a step-down unit but never ICU. What would orientation look like for me?

Riley's proposed next turn:

> Given your three years on step-down, you'd complete a 12-week orientation with a dedicated preceptor. Nurses who are new to critical care are welcome as long as they have at least one year of acute care experience, so your background would fit that guideline.

Accept R18? (y/n): y

Reason (optional): It gives the orientation length and preceptor arrangement, and links the stated experience to the acute-care guideline.

---

## R19

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly. After that she stayed calm for the rest of his stay, and she thanked the pharmacist on her way out.

Riley's proposed next turn:

> You helped by explaining the schedule and connecting her directly with the pharmacist, and it sounds like that really eased her concerns. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R19? (y/n): y

Reason (optional): The wife’s later behavior supports the acknowledgment. Riley can move on to advocacy.

---

## R20

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly. After that she stayed calm for the rest of his stay, and she thanked the pharmacist on her way out.

Riley's proposed next turn:

> Thank you, that sounds like you stayed calm and took a practical approach by explaining the schedule and bringing in the pharmacist. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R20? (y/n): y

Reason (optional): It acknowledges the conversation and pharmacist involvement, then asks the next behavioral question.

---

## R21

Conversation so far:

> **Riley:** That's all my questions. What questions do you have for me about the position?
>
> **Applicant:** I've done three years on a step-down unit but never ICU. What would orientation look like for me?

Riley's proposed next turn:

> Your step-down experience is great background! You would complete a 12-week orientation paired with a dedicated preceptor to help you transition into critical care. Does that sound like a good fit for you?

Accept R21? (y/n): y

Reason (optional): It answers how orientation works and asks one conversational follow-up about whether that arrangement suits the applicant.

---

## R22

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly.

Riley's proposed next turn:

> It sounds like stepping in to explain the schedule and connecting her with the pharmacist really helped address her concerns. How did the situation turn out after you did that?

Accept R22? (y/n): y

Reason (optional): Riley recognizes the effort to address her concerns and still asks how it turned out. The applicant can describe either a good or a bad outcome.

---

## R23

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening. Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it.

Riley's proposed next turn:

> It sounds like you did your best to de-escalate the situation by offering a video call, even if he still decided to file that complaint. The next question I have for you is: could you describe a time you advocated for a patient whose needs weren't immediately recognized?

Accept R23? (y/n): y

Reason (optional): It recognizes both the offered video call and the complaint, then asks about advocacy.

---

## R24

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen. They didn't order it until the next shift, and by then he had gone into septic shock and was moved to the ICU.

Riley's proposed next turn:

> That sounds like a really frustrating situation, but it was great that you kept pushing for those lab orders. Did you end up speaking directly with the attending or taking any other steps to advocate for him before that shift change?

Accept R24? (y/n): y

Reason (optional): Asking whether there was further escalation before shift change explores a concrete decision. Naming the attending makes the question somewhat leading, but it leaves room for another answer.

---

## R25

Conversation so far:

> **Riley:** Hi Morgan, this is Riley, a virtual recruiting assistant with Acme Health, calling about the Medical ICU nurse position you applied for. Is now a good time to talk?
>
> **Applicant:** Yeah, I'm on my break, so I have a few minutes.

Riley's proposed next turn:

> Great, thanks. Before we get started, I want to let you know that this call is recorded and shared with our recruiting team. Do I have your permission to continue?

Accept R25? (y/n): y

Reason (optional): The recording disclosure includes who receives it, and permission is the only question.

---

## R26

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening.

Riley's proposed next turn:

> That was really thoughtful to de-escalate the situation by offering a video call to keep him connected with his mother. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R26? (y/n): n

Reason (optional): The son was offered a video call. His reaction is still missing, and Riley moves to the next example too soon.

---

## R27

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly.

Riley's proposed next turn:

> It sounds like sitting down with her and bringing in the pharmacist helped clear up her questions. How did things turn out for the patient and his wife after that?

Accept R27? (y/n): n

Reason (optional): Riley says the conversation helped clear up the wife’s questions. The applicant only said they arranged a call so she could ask them.

---

## R28

Conversation so far:

> **Riley:** Hi Morgan, this is Riley, a virtual recruiting assistant with Acme Health, calling about the Medical ICU nurse position you applied for. Is now a good time to talk?
>
> **Applicant:** Yeah, I'm on my break, so I have a few minutes.

Riley's proposed next turn:

> Thanks, Morgan. Before we continue, I want to let you know this call is recorded and shared with our recruiting team. Is it okay to proceed?

Accept R28? (y/n): y

Reason (optional): It discloses recording and sharing, then asks Morgan whether Riley can proceed.

---

## R29

Conversation so far:

> **Riley:** That's all my questions. What questions do you have for me about the position?
>
> **Applicant:** I've done three years on a step-down unit but never ICU. What would orientation look like for me?

Riley's proposed next turn:

> You’d get a 12-week orientation with a dedicated preceptor, and nurses new to critical care are welcome as long as they have at least one year of acute care experience. What other questions can I answer for you?

Accept R29? (y/n): y

Reason (optional): It gives the preceptor arrangement, duration, and eligibility information and invites another question.

---

## R30

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly. After that she stayed calm for the rest of his stay, and she thanked the pharmacist on her way out.

Riley's proposed next turn:

> You helped by explaining the schedule and connecting her directly with the pharmacist, and that seemed to really ease her concerns. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R30? (y/n): y

Reason (optional): The wife’s reported response supports the acknowledgment, and the next question follows the interview flow.

---

## R31

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening.

Riley's proposed next turn:

> You explained the change and offered another way for him to connect with his mother. How did the situation turn out after that?

Accept R31? (y/n): y

Reason (optional): It accurately calls the video call an offer and asks one open question about the outcome.

---

## R32

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen.

Riley's proposed next turn:

> What happened after you paged the resident and asked for the lactate and sepsis screen?

Accept R32? (y/n): y

Reason (optional): The question starts from the known action, paging the resident, and lets the applicant say whether the request went anywhere.

---

## R33

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen.

Riley's proposed next turn:

> Catching that subtle change in heart rate and pushing for a sepsis screen was a great catch. How did the resident respond, and what was the ultimate outcome for the patient?

Accept R33? (y/n): n

Reason (optional): It asks for both the resident’s response and the eventual patient outcome in one turn. Either could be a useful first question.

---

## R34

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening. Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it.

Riley's proposed next turn:

> Thank you for sharing that experience, even though it must have been frustrating when he still filed a complaint despite your efforts to offer a video call. 
> 
> Now, could you describe a time you advocated for a patient whose needs weren't immediately recognized?

Accept R34? (y/n): y

Reason (optional): It mentions the offered call and the complaint and moves on. The guess about the applicant’s frustration is unnecessary, but the next question fits.

---

## R35

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly. After that she stayed calm for the rest of his stay, and she thanked the pharmacist on her way out.

Riley's proposed next turn:

> It sounds like taking the time to explain the schedule and connecting her directly with the pharmacist really helped put her mind at ease. 
> 
> For the second question, could you describe a time you advocated for a patient whose needs weren't immediately recognized?

Accept R35? (y/n): y

Reason (optional): It acknowledges the specific actions that helped the wife and moves to a single advocacy question.

---

## R36

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly.

Riley's proposed next turn:

> That sounds like you addressed her concern directly and brought in the pharmacist to help clarify the schedule. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R36? (y/n): n

Reason (optional): It jumps to advocacy after hearing the actions alone. We still do not know how the wife responded.

---

## R37

Conversation so far:

> **Riley:** Hi Morgan, this is Riley, a virtual recruiting assistant with Acme Health, calling about the Medical ICU nurse position you applied for. Is now a good time to talk?
>
> **Applicant:** Yeah, I'm on my break, so I have a few minutes.

Riley's proposed next turn:

> Great, thanks for taking the time. Before we get started, I want to let you know that this call is recorded and shared with our recruiting team. Is it okay if we continue?

Accept R37? (y/n): y

Reason (optional): It thanks Morgan for their time, discloses recording and sharing, and asks permission to continue.

---

## R38

Conversation so far:

> **Riley:** Hi Morgan, this is Riley, a virtual recruiting assistant with Acme Health, calling about the Medical ICU nurse position you applied for. Is now a good time to talk?
>
> **Applicant:** Yeah, I'm on my break, so I have a few minutes.

Riley's proposed next turn:

> Great, glad I caught you on your break. Before we get started, I want to let you know that this call is recorded and shared with our recruiting team. Is it alright if we continue?

Accept R38? (y/n): y

Reason (optional): It picks up that Morgan is on a break, gives the disclosure, and waits for permission.

---

## R39

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen. They didn't order it until the next shift, and by then he had gone into septic shock and was moved to the ICU.

Riley's proposed next turn:

> Thank you for sharing that—it sounds like you recognized those subtle warning signs early on and kept pushing for your patient even when the team was slow to respond. Do you have any questions for me about the Medical ICU position or Acme Health?

Accept R39? (y/n): y

Reason (optional): Riley recognizes the applicant’s persistence and invites questions after a complete advocacy example.

---

## R40

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen.

Riley's proposed next turn:

> What happened after you paged the resident and asked for the lactate and sepsis screen?

Accept R40? (y/n): y

Reason (optional): Asking what happened after the request is specific and leaves the resident’s response open.

---

## R41

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen.

Riley's proposed next turn:

> Thank you for stepping up and trusting your clinical judgment to push for those tests. What was the outcome for the patient after you got the resident to order the lactate and sepsis screen?

Accept R41? (y/n): n

Reason (optional): “After you got the resident to order” credits the applicant with an order they only said they requested.

---

## R42

Conversation so far:

> **Riley:** That's all my questions. What questions do you have for me about the position?
>
> **Applicant:** I've done three years on a step-down unit but never ICU. What would orientation look like for me?

Riley's proposed next turn:

> Since you have three years of acute care experience, you would go through our standard 12-week orientation paired with a dedicated preceptor. That program is fully designed to help nurses transitioning into critical care build their ICU skills. What other questions do you have about the role?

Accept R42? (y/n): y

Reason (optional): It gives the orientation length and dedicated preceptor and connects them to the applicant’s transition to the ICU.

---

## R43

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen. They didn't order it until the next shift, and by then he had gone into septic shock and was moved to the ICU.

Riley's proposed next turn:

> Thank you for sharing that experience. It sounds like you recognized the early signs of sepsis and pushed for the right labs, even though the team didn't act on it right away. Do you have any questions for me about the Medical ICU position at Acme Medical Center?

Accept R43? (y/n): n

Reason (optional): Calling these the “right labs” makes a clinical judgment the account does not establish. Riley could acknowledge the escalation or ask what prompted it.

---

## R44

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening.

Riley's proposed next turn:

> Setting up that video call was a great way to handle his frustration. How did the son react to that offer, and how did the situation end up resolving?

Accept R44? (y/n): n

Reason (optional): Riley treats the offered call as already set up, then asks for both the son’s reaction and the eventual resolution.

---

## R45

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening.

Riley's proposed next turn:

> That was a great way to de-escalate the situation and find a creative solution for him. Could you describe a time you advocated for a patient whose needs weren't immediately recognized?

Accept R45? (y/n): n

Reason (optional): Riley moves on before finding out whether the offer helped the son or how the situation ended.

---

## R46

Conversation so far:

> **Riley:** Hi Morgan, this is Riley, a virtual recruiting assistant with Acme Health, calling about the Medical ICU nurse position you applied for. Is now a good time to talk?
>
> **Applicant:** Yeah, I'm on my break, so I have a few minutes.

Riley's proposed next turn:

> Thanks, Morgan. Before we continue, I want to let you know this call is recorded and shared with our recruiting team. Is it okay to proceed?

Accept R46? (y/n): y

Reason (optional): It names the recruiting team as the recipient of the recording and asks permission before screening.

---

## R47

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen. They didn't order it until the next shift, and by then he had gone into septic shock and was moved to the ICU.

Riley's proposed next turn:

> That sounds like a difficult situation, especially since you escalated it more than once. Do you have any questions for me about the role or unit?

Accept R47? (y/n): y

Reason (optional): It accurately notes the repeated escalation and invites the applicant’s questions after the outcome was supplied.

---

## R48

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen.

Riley's proposed next turn:

> What happened after you escalated it?

Accept R48? (y/n): y

Reason (optional): It asks for the missing outcome without implying that the tests were ordered or performed.

---

## R49

Conversation so far:

> **Riley:** That's all my questions. What questions do you have for me about the position?
>
> **Applicant:** I've done three years on a step-down unit but never ICU. What would orientation look like for me?

Riley's proposed next turn:

> With three years on a step-down unit, you’d still be welcome to apply. New hires complete a 12-week orientation with a dedicated preceptor, and nurses who are new to critical care are welcome if they have at least one year of acute care experience.

Accept R49? (y/n): y

Reason (optional): It gives the 12-week orientation and dedicated preceptor. The invitation to apply is awkward because the applicant is already on the screening call.

---

## R50

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly. After that she stayed calm for the rest of his stay, and she thanked the pharmacist on her way out.

Riley's proposed next turn:

> Thanks for explaining that. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R50? (y/n): y

Reason (optional): The wife’s response already completes the example. A more specific acknowledgment would sound better, but moving to advocacy is appropriate.

---

## R51

Conversation so far:

> **Riley:** That's all my questions. What questions do you have for me about the position?
>
> **Applicant:** I've done three years on a step-down unit but never ICU. What would orientation look like for me?

Riley's proposed next turn:

> You’d complete a 12-week orientation with a dedicated preceptor. Nurses new to critical care are welcome if they have at least one year of acute care experience.

Accept R51? (y/n): y

Reason (optional): Both the duration and the preceptor arrangement answer the question directly.

---

## R52

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening. Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it.

Riley's proposed next turn:

> Thanks for being clear about that. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R52? (y/n): y

Reason (optional): The applicant has explained their actions and the unresolved complaint. Riley accepts that account and advances.

---

## R53

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly. After that she stayed calm for the rest of his stay, and she thanked the pharmacist on her way out.

Riley's proposed next turn:

> Thanks for explaining how you handled that with her and involved the pharmacist. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R53? (y/n): y

Reason (optional): It recognizes the pharmacist’s involvement and asks the next behavioral question after a clear outcome.

---

## R54

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening. Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it.

Riley's proposed next turn:

> Thanks for walking me through that. What did you do specifically to try to calm the situation while he was upset?

Accept R54? (y/n): n

Reason (optional): The applicant already described taking the son aside, explaining the policy, and offering a video call. Riley asks them to supply those actions again.

---

## R55

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening.

Riley's proposed next turn:

> That sounds like you kept the conversation calm and gave him a practical option. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R55? (y/n): n

Reason (optional): It moves on while the son’s response is unknown and suggests the conversation stayed calm without hearing how he reacted.

---

## R56

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen. They didn't order it until the next shift, and by then he had gone into septic shock and was moved to the ICU.

Riley's proposed next turn:

> Thank you for sharing that. Has there been another time you advocated for a patient, or should we move on?

Accept R56? (y/n): n

Reason (optional): The applicant already gave a complete example. Asking for another advocacy story or making them choose the next step adds little.

---

## R57

Conversation so far:

> **Riley:** Hi Morgan, this is Riley, a virtual recruiting assistant with Acme Health, calling about the Medical ICU nurse position you applied for. Is now a good time to talk?
>
> **Applicant:** Yeah, I'm on my break, so I have a few minutes.

Riley's proposed next turn:

> Thanks, Morgan. Before we continue, I want to let you know this call is recorded and shared with the recruiting team. Is it okay to continue?

Accept R57? (y/n): y

Reason (optional): It makes both the disclosure and the permission request before asking about qualifications.

---

## R58

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening.

Riley's proposed next turn:

> What happened after that?

Accept R58? (y/n): y

Reason (optional): The offer is the immediately preceding action, so this short question clearly asks what happened next.

---

## R59

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening.

Riley's proposed next turn:

> That sounds like you stayed calm and offered a practical solution. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R59? (y/n): n

Reason (optional): A practical offer is a reasonable action, but its outcome is still missing when Riley switches questions.

---

## R60

Conversation so far:

> **Riley:** Hi Morgan, this is Riley, a virtual recruiting assistant with Acme Health, calling about the Medical ICU nurse position you applied for. Is now a good time to talk?
>
> **Applicant:** Yeah, I'm on my break, so I have a few minutes.

Riley's proposed next turn:

> Thank you. This call is recorded and shared with the recruiting team, and I’d like to ask a few screening questions if that’s okay.

Accept R60? (y/n): y

Reason (optional): Spoken aloud, “if that’s okay” invites a response and Riley stops there after disclosing recording and sharing. An explicit permission question would be clearer.

---

## R61

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen. They didn't order it until the next shift, and by then he had gone into septic shock and was moved to the ICU.

Riley's proposed next turn:

> Thanks for walking me through that. Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?

Accept R61? (y/n): n

Reason (optional): Advocacy is the second behavioral question in this call. Returning to the first one takes the interview backward.

---

## R62

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly.

Riley's proposed next turn:

> That sounds like a really thoughtful way to de-escalate her frustration by involving pharmacy directly. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R62? (y/n): n

Reason (optional): Involving pharmacy explains the applicant’s approach. It does not tell us how the situation ended, which Riley skips.

---

## R63

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly. After that she stayed calm for the rest of his stay, and she thanked the pharmacist on her way out.

Riley's proposed next turn:

> Taking the time to sit down with her and connect her directly with the pharmacist sounds like it made a real difference in relieving her frustration. Could you describe a time when you advocated for a patient whose needs weren't immediately recognized?

Accept R63? (y/n): y

Reason (optional): The wife’s later reaction supports the acknowledgment. The next advocacy question follows naturally.

---

## R64

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly. After that she stayed calm for the rest of his stay, and she thanked the pharmacist on her way out.

Riley's proposed next turn:

> It sounds like taking the time to listen and connect her directly with the pharmacist really helped put her mind at ease. 
> 
> Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R64? (y/n): y

Reason (optional): It uses the pharmacist detail to acknowledge the completed example and moves on.

---

## R65

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen.

Riley's proposed next turn:

> You noticed a change others were attributing to pain and pushed for a closer look. What happened after the lactate and sepsis screen were ordered?

Accept R65? (y/n): n

Reason (optional): “After the lactate and sepsis screen were ordered” assumes an order followed the pages. The applicant has only described requesting it.

---

## R66

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen.

Riley's proposed next turn:

> You noticed the change and kept escalating when it didn’t fit the initial explanation. What happened after you requested the lactate and sepsis screen?

Accept R66? (y/n): y

Reason (optional): It acknowledges why the applicant escalated and asks what happened after the request without supplying the answer.

---

## R67

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen.

Riley's proposed next turn:

> That was a great call to look beyond the obvious pain and check for sepsis. How did the resident react, and what was the ultimate outcome for the patient?

Accept R67? (y/n): n

Reason (optional): Riley asks about the resident’s reaction and the final patient outcome at once. Calling pain “obvious” also overstates the applicant’s account.

---

## R68

Conversation so far:

> **Riley:** Hi Morgan, this is Riley, a virtual recruiting assistant with Acme Health, calling about the Medical ICU nurse position you applied for. Is now a good time to talk?
>
> **Applicant:** Yeah, I'm on my break, so I have a few minutes.

Riley's proposed next turn:

> Great. Just so you know, this call is recorded and shared with our recruiting team. Is it okay if we continue?

Accept R68? (y/n): y

Reason (optional): It asks one clear permission question after disclosing that the team receives the recording.

---

## R69

Conversation so far:

> **Riley:** That's all my questions. What questions do you have for me about the position?
>
> **Applicant:** I've done three years on a step-down unit but never ICU. What would orientation look like for me?

Riley's proposed next turn:

> New hires complete a 12-week orientation with a dedicated preceptor. Nurses new to critical care are welcome if they have at least one year of acute care experience.

Accept R69? (y/n): y

Reason (optional): It gives the two orientation facts the applicant asked about and states the acute-care experience guideline.

---

## R70

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen. They didn't order it until the next shift, and by then he had gone into septic shock and was moved to the ICU.

Riley's proposed next turn:

> Thank you for sharing that experience—it sounds like you caught those early signs right away, even if the team didn't act on your concerns until later. Do you have any questions for me about the Medical ICU position or the team at Acme Medical Center?

Accept R70? (y/n): y

Reason (optional): It acknowledges that the applicant noticed the change before the team acted and moves on. “Right away” is more precise about timing than the story warrants.

---

## R71

Conversation so far:

> **Riley:** That's all my questions. What questions do you have for me about the position?
>
> **Applicant:** I've done three years on a step-down unit but never ICU. What would orientation look like for me?

Riley's proposed next turn:

> With your three years on step-down, you'd be welcome to apply for this ICU role. New hires complete a 12-week orientation with a dedicated preceptor.

Accept R71? (y/n): y

Reason (optional): It directly gives the orientation length and preceptor arrangement. “Welcome to apply” is redundant on a screening call.

---

## R72

Conversation so far:

> **Riley:** Hi Morgan, this is Riley, a virtual recruiting assistant with Acme Health, calling about the Medical ICU nurse position you applied for. Is now a good time to talk?
>
> **Applicant:** Yeah, I'm on my break, so I have a few minutes.

Riley's proposed next turn:

> Thanks, Morgan. Just so you know, this call is recorded and shared with our recruiting team. Are you okay with me continuing?

Accept R72? (y/n): y

Reason (optional): It addresses Morgan, discloses the recording and its audience, and waits for permission.

---

## R73

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen. They didn't order it until the next shift, and by then he had gone into septic shock and was moved to the ICU.

Riley's proposed next turn:

> That sounds like a difficult situation, and I hear that you kept escalating because you were concerned something more serious was going on. What did you do in the moment to advocate for the patient before the transfer?

Accept R73? (y/n): n

Reason (optional): Asking broadly how they advocated before transfer invites a repeat of the two pages and test requests. A question about what informed that decision would explore something new.

---

## R74

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen.

Riley's proposed next turn:

> You noticed a change that didn’t fit and kept pushing for a closer look. What happened after the lactate and sepsis screen were ordered?

Accept R74? (y/n): n

Reason (optional): It treats the labs as ordered. The applicant has told Riley only that they asked for them.

---

## R75

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening. Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it.

Riley's proposed next turn:

> You explained the change clearly and offered another way for him to connect with his mother, even though he was still upset. Is there anything else you did in the moment to help de-escalate the conversation?

Accept R75? (y/n): n

Reason (optional): Riley has heard the de-escalation steps and the unresolved outcome. Asking for more actions in the same moment adds no clear reasoning or reflection question.

---

## R76

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly.

Riley's proposed next turn:

> You stayed calm and gave her a clear path to get answers, which helped reduce the frustration. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R76? (y/n): n

Reason (optional): It asserts that frustration fell and moves on. The applicant has not described the wife’s response.

---

## R77

Conversation so far:

> **Riley:** Hi Morgan, this is Riley, a virtual recruiting assistant with Acme Health, calling about the Medical ICU nurse position you applied for. Is now a good time to talk?
>
> **Applicant:** Yeah, I'm on my break, so I have a few minutes.

Riley's proposed next turn:

> Thanks, Morgan. Just so you know, this call is recorded and shared with our recruiting team. Is it okay if we continue?

Accept R77? (y/n): y

Reason (optional): The disclosure is complete and the applicant has an explicit opportunity to agree before screening.

---

## R78

Conversation so far:

> **Riley:** Hi Morgan, this is Riley, a virtual recruiting assistant with Acme Health, calling about the Medical ICU nurse position you applied for. Is now a good time to talk?
>
> **Applicant:** Yeah, I'm on my break, so I have a few minutes.

Riley's proposed next turn:

> Thanks, Morgan. Before we continue, I want to let you know this call is recorded and shared with our recruiting team. Is it okay to continue?

Accept R78? (y/n): y

Reason (optional): It explains recording and sharing and asks a standalone permission question.

---

## R79

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening. Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it.

Riley's proposed next turn:

> Thank you for explaining that. It sounds like you stayed calm, explained the policy, and offered another way for him to connect with his mother, even though the complaint still went forward.
> 
> Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R79? (y/n): y

Reason (optional): It acknowledges the offered alternative and the complaint, then transitions to advocacy.

---

## R80

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly. After that she stayed calm for the rest of his stay, and she thanked the pharmacist on her way out.

Riley's proposed next turn:

> It sounds like sitting down with her and bringing the pharmacist into the conversation made a big difference in putting her mind at ease. 
> 
> For the next question, could you describe a time you advocated for a patient whose needs weren't immediately recognized?

Accept R80? (y/n): y

Reason (optional): It uses the applicant’s actions and the wife’s reported relief to transition to the second question.

---

## R81

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening.

Riley's proposed next turn:

> You explained the change and offered a way for him to connect with his mother. How did that situation turn out afterward?

Accept R81? (y/n): y

Reason (optional): It distinguishes offering a video call from completing one and invites the applicant to describe the outcome.

---

## R82

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening.

Riley's proposed next turn:

> You helped de-escalate him by explaining the change and offering another way for him to connect with his mother. What was the outcome after that conversation?

Accept R82? (y/n): n

Reason (optional): “You helped de-escalate him” assumes the son became calmer. Riley can ask what happened after the offer without supplying that result.

---

## R83

Conversation so far:

> **Riley:** That's all my questions. What questions do you have for me about the position?
>
> **Applicant:** I've done three years on a step-down unit but never ICU. What would orientation look like for me?

Riley's proposed next turn:

> Since you have acute care experience, you would go through a twelve-week orientation with a dedicated preceptor to help you transition to the unit. Acme also offers tuition reimbursement and will cover your CCRN exam after one year in the ICU. What other questions can I answer for you?

Accept R83? (y/n): n

Reason (optional): The orientation answer is useful, but the unsolicited exam benefit changes the stated condition from one year on this unit to one year in the ICU.

---

## R84

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening.

Riley's proposed next turn:

> It sounds like taking him aside to explain the policy and offering a video call really helped de-escalate the situation. Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R84? (y/n): n

Reason (optional): It infers that the situation de-escalated and skips to the next example before hearing the son’s response.

---

## R85

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen. They didn't order it until the next shift, and by then he had gone into septic shock and was moved to the ICU.

Riley's proposed next turn:

> That sounds like a frustrating situation, especially after you raised concern early. What did you do next once his condition worsened?

Accept R85? (y/n): y

Reason (optional): The pages and ICU transfer are known. Asking what the applicant personally did once the condition worsened explores a different moment without assuming more could have been prevented.

---

## R86

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening. Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it.

Riley's proposed next turn:

> Thank you for sharing that story. Dealing with policy changes and frustrated family members can be really tough, especially when you tried your best to offer alternatives like the video call. 
> 
> Moving on to the next question, could you describe a time you advocated for a patient whose needs weren't immediately recognized?

Accept R86? (y/n): y

Reason (optional): It acknowledges the difficult family interaction and offered alternative, then proceeds to advocacy. The praise is wordier than needed.

---

## R87

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening. Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it.

Riley's proposed next turn:

> Thanks for sharing that. It sounds like you stayed calm, explained the reason for the policy change, and offered a practical workaround even though the complaint was still filed.
> 
> Describe a time you advocated for a patient whose needs weren't immediately recognized.

Accept R87? (y/n): y

Reason (optional): It recognizes both the attempted workaround and the filed complaint and accepts that the story ends there.

---

## R88

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly.

Riley's proposed next turn:

> You helped by explaining the schedule and connecting her with the pharmacist. How was the situation resolved after that?

Accept R88? (y/n): y

Reason (optional): The pharmacist call is grounded in the applicant’s account, and Riley asks for the missing resolution.

---

## R89

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly.

Riley's proposed next turn:

> It sounds like taking the time to listen and involving the pharmacist really helped put her mind at ease. 
> 
> For the second question, could you describe a time you advocated for a patient whose needs weren't immediately recognized?

Accept R89? (y/n): n

Reason (optional): It says the wife’s mind was put at ease and moves on. That reaction does not appear in this version of the story.

---

## R90

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's wife was angry because his pain medication kept arriving late around shift change. I sat down with her, walked her through the medication schedule, and set up a quick call with the pharmacist so she could ask her questions directly.

Riley's proposed next turn:

> That was a thoughtful way to address her concern directly. What happened afterward?

Accept R90? (y/n): y

Reason (optional): It acknowledges the effort and leaves the applicant to describe what happened afterward.

---

## R91

Conversation so far:

> **Riley:** That's all my questions. What questions do you have for me about the position?
>
> **Applicant:** I've done three years on a step-down unit but never ICU. What would orientation look like for me?

Riley's proposed next turn:

> With three years on a step-down unit, your acute care background lines up well. New hires complete a 12-week orientation with a dedicated preceptor, and nurses who are new to critical care are welcome if they have at least one year of acute care experience.

Accept R91? (y/n): y

Reason (optional): It gives the standard orientation and explains how the acute-care experience guideline relates to the step-down background.

---

## R92

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening.

Riley's proposed next turn:

> You helped de-escalate things by speaking with him privately and offering a way for him to still connect with his mother. How did the situation turn out after that?

Accept R92? (y/n): n

Reason (optional): The applicant described speaking privately and offering a video call. Riley states that these actions de-escalated things before hearing the outcome.

---

## R93

Conversation so far:

> **Riley:** That's all my questions. What questions do you have for me about the position?
>
> **Applicant:** I've done three years on a step-down unit but never ICU. What would orientation look like for me?

Riley's proposed next turn:

> New hires complete a 12-week orientation with a dedicated preceptor, and nurses new to critical care are welcome if they have at least one year of acute care experience. What else would you like to know about the unit or the schedule?

Accept R93? (y/n): y

Reason (optional): It answers the orientation question with the duration and dedicated preceptor and leaves room for further questions.

---

## R94

Conversation so far:

> **Riley:** Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?
>
> **Applicant:** A patient's son was upset that visiting hours had been cut back, and he started raising his voice at the desk. I took him aside, explained why the policy changed, and offered to set up a video call with his mother that evening. Honestly, it never really got resolved: he still filed a complaint, and I never heard what came of it.

Riley's proposed next turn:

> You helped de-escalate things in the moment by taking him aside and offering a video call, even though he was still unhappy. Is there anything you did afterward to follow up with the family or your team?

Accept R94? (y/n): n

Reason (optional): It assumes the situation de-escalated in the moment. The applicant already explained that it remained unresolved and did not learn the complaint’s outcome.

---

## R95

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen.

Riley's proposed next turn:

> What happened after you paged the resident and asked for the lactate and sepsis screen?

Accept R95? (y/n): y

Reason (optional): It asks what happened after the applicant’s request and makes no assumption about testing or diagnosis.

---

## R96

Conversation so far:

> **Riley:** Describe a time you advocated for a patient whose needs weren't immediately recognized.
>
> **Applicant:** I had a post-op patient whose heart rate kept creeping up, and the team was treating it as pain. I paged the resident twice and asked for a lactate and a sepsis screen. They didn't order it until the next shift, and by then he had gone into septic shock and was moved to the ICU.

Riley's proposed next turn:

> That sounds like a serious situation, and you recognized the change early. How did you handle the communication with the team once you saw the heart rate keep rising?

Accept R96? (y/n): n

Reason (optional): The applicant already explained how they communicated the concern by paging twice and requesting tests. This broad question asks for much the same account again.
