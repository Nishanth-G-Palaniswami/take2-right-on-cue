# H2 criteria experiment: blind label sheet

Label each reply as Riley's next turn: `y` if it is an acceptable next turn, `n` if not, by your own judgment.

- Each item shows the conversation so far and one proposed reply. Several items share a conversation.
- The items are new, written by a separate agent from your description of the rule. What each reply was written to do is sealed in `holdout-private/h2-criteria/` and committed by hash.
- Please label every item before opening `holdout-private/h2-criteria/`, the plan's item table, or any score. Scoring refuses to start until every Accept line has y or n.
- A reason is optional. Note below whether you used an AI assistant.

Used an AI assistant while labelling (yes/no): yes

Reviewed in full by Nishanth. ChatGPT drafted the labels and reasons using my guidance from earlier reviews. I then personally checked all 19 transcripts, proposed replies, labels, and reasons.

---

## K01

Conversation so far:

> **Riley:** Hi, I'm Riley, a virtual recruiting assistant with Acme Health in Denver, calling about the Medical ICU nurse role. Just so you know, this call is recorded and shared with our recruiting team. Is it all right to go on?
>
> **Applicant:** Yes, that works for me.
>
> **Riley:** Thank you, Lucia. First, do you have an active Colorado RN license or an active multistate license?
>
> **Applicant:** Yes, I have an active multistate license through my home state.
>
> **Riley:** Perfect. And what certifications do you hold?
>
> **Applicant:** Well, I've got BLS and ACLS, and back in 2019 I did a PALS course when my hospital was cross-training us for the children's unit.

Riley's proposed next turn:

> Nice, the pediatric cross-training sounds useful. Let's turn to a few experience questions. Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?

Accept K01? (y/n): n

Reason (optional): Lucia lists BLS and ACLS alongside a PALS course from 2019. Riley moves to the behavioral question before confirming whether both required credentials are current.

---

## K02

Conversation so far:

> **Riley:** Hello, this is Riley, a virtual recruiting assistant for Acme Health in Denver. I'm calling about our Medical ICU nurse position. This call is recorded and shared with the recruiting team. Are you comfortable continuing?
>
> **Applicant:** Yes, I'm comfortable with that.
>
> **Riley:** Great, Fiona. Can you tell me about your nursing license and your certifications?
>
> **Applicant:** My Colorado RN license is active. I recertified my BLS and ACLS last month, so both are good for another two years. I also hold my CCRN.

Riley's proposed next turn:

> Congratulations on the CCRN, that's a real plus for an ICU. Have you also completed the NIH Stroke Scale certification?

Accept K02? (y/n): y

Reason (optional): Fiona confirmed an active license, recent renewal of both required credentials, and her CCRN. Riley acknowledges the CCRN and asks about one credential she has not mentioned.

---

## K03

Conversation so far:

> **Riley:** Hello, this is Riley, a virtual recruiter for Acme Health in Denver. I'm phoning about our Medical ICU registered nurse opening. We record this call and share it with the recruiting team. Do you agree to continue?
>
> **Applicant:** Yeah, I agree. Go ahead.
>
> **Riley:** Thanks, Grant. Do you currently hold an active Colorado RN license, or an active compact license?
>
> **Applicant:** I do, my Colorado license is active.
>
> **Riley:** Good to hear. Which certifications do you have?
>
> **Applicant:** I hold BLS and ACLS, plus I took an NIH Stroke Scale class around 2018 at my old hospital in Phoenix.

Riley's proposed next turn:

> Thanks, that gives me a good picture. Now, tell me about a time you managed an upset patient or family member. What happened, and how did you resolve it?

Accept K03? (y/n): n

Reason (optional): Grant names BLS and ACLS and describes a class from 2018. Riley still needs to confirm that both required credentials are current before moving on.

---

## K04

Conversation so far:

> **Riley:** Hello, I'm Riley, a virtual recruiter for Acme Health in Denver. I'm calling about our Medical ICU registered nurse position. We record this call and share it with the recruiting team. Do you agree to go ahead?
>
> **Applicant:** Yes, that's fine with me.
>
> **Riley:** Great, Sabine. Can you tell me about your license and your BLS and ACLS?
>
> **Applicant:** Sure. I have an active multistate RN license, and I renewed both my BLS and ACLS just a few weeks ago.

Riley's proposed next turn:

> Wonderful. Do you hold CCRN or PALS? Also, tell me about a time you managed an upset patient or family member, and how it was resolved.

Accept K04? (y/n): n

Reason (optional): Sabine’s recent renewals settle the required credentials. Either proposed topic works on its own, but Riley asks for a certification answer and a behavioral story in the same turn.

---

## K05

Conversation so far:

> **Riley:** Hi, this is Riley, a virtual recruiting assistant with Acme Health in Denver, calling about the Medical ICU nurse opening. This call is recorded and shared with our recruiting team. Is it okay to continue?
>
> **Applicant:** Yes, no problem.
>
> **Riley:** Thanks, Hollis. Let's talk credentials. Do you have an active Colorado RN license or an active multistate license, and what's the status of your BLS and ACLS?
>
> **Applicant:** My Colorado RN license is active, and my BLS and ACLS cards are both valid through the end of next June.

Riley's proposed next turn:

> Perfect, thank you. Do you also hold any extra certifications like CCRN, PALS, or the NIH Stroke Scale?

Accept K05? (y/n): y

Reason (optional): Hollis gave a future validity date for both cards. The three examples help Hollis answer one question about additional certifications.

---

## K06

Conversation so far:

> **Riley:** Hi, this is Riley, a virtual recruiting assistant with Acme Health in Denver, calling about the Medical ICU nurse opening. Before we start, I should let you know this call is recorded and shared with our recruiting team. Is that okay with you?
>
> **Applicant:** Sure, that's fine, go ahead.
>
> **Riley:** Thanks, Joaquin. Let's start with your credentials. Do you hold an active Colorado RN license or an active multistate license, and are your BLS and ACLS up to date?
>
> **Applicant:** Yes, I have an active Colorado RN license, and my BLS and ACLS are both current.

Riley's proposed next turn:

> Wonderful, that's exactly what we need. Let's move to a couple of questions about your experience. Tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?

Accept K06? (y/n): y

Reason (optional): Joaquin explicitly confirmed his active license and both current certifications. Riley can move on and ask for the family-member example.

---

## K07

Conversation so far:

> **Riley:** Hi, this is Riley, a virtual recruiting assistant with Acme Health in Denver, calling about the Medical ICU nurse opening. Before we start, I should let you know this call is recorded and shared with our recruiting team. Is that okay with you?
>
> **Applicant:** Sure, that's fine, go ahead.
>
> **Riley:** Thanks, Joaquin. Let's start with your credentials. Do you hold an active Colorado RN license or an active multistate license, and are your BLS and ACLS up to date?
>
> **Applicant:** Yes, I have an active Colorado RN license, and my BLS and ACLS are both current.

Riley's proposed next turn:

> Great, thanks for confirming. Do you hold any of the extras we like to see in the ICU, such as CCRN or the NIH Stroke Scale?

Accept K07? (y/n): y

Reason (optional): Joaquin has confirmed the required credentials. Riley asks one focused question about optional credentials he has not mentioned.

---

## K08

Conversation so far:

> **Riley:** Hi, this is Riley, a virtual recruiting assistant with Acme Health in Denver, calling about the Medical ICU nurse opening. Before we start, I should let you know this call is recorded and shared with our recruiting team. Is that okay with you?
>
> **Applicant:** Sure, that's fine, go ahead.
>
> **Riley:** Thanks, Joaquin. Let's start with your credentials. Do you hold an active Colorado RN license or an active multistate license, and are your BLS and ACLS up to date?
>
> **Applicant:** Yes, I have an active Colorado RN license, and my BLS and ACLS are both current.

Riley's proposed next turn:

> Good to hear. Do you also have CCRN or PALS? And then tell me about a time you managed an upset patient or family member, and how it was resolved.

Accept K08? (y/n): n

Reason (optional): Riley asks Joaquin to answer a credential question and tell a separate story before he has had a chance to respond to either.

---

## K09

Conversation so far:

> **Riley:** Hello, I'm Riley, a virtual recruiter for Acme Health in Denver. I'm calling about our Medical ICU registered nurse position. We record this call and share it with the recruiting team. Do you agree to go ahead?
>
> **Applicant:** Yes, that's fine with me.
>
> **Riley:** Great, Sabine. Can you tell me about your license and your BLS and ACLS?
>
> **Applicant:** Sure. I have an active multistate RN license, and I renewed both my BLS and ACLS just a few weeks ago.

Riley's proposed next turn:

> Good to hear, and thanks for that. Have you earned anything beyond those, such as CCRN, PALS, or NIH Stroke Scale certification?

Accept K09? (y/n): y

Reason (optional): Sabine renewed both credentials a few weeks ago. Riley can ask one question about any additional certifications, using the three credentials as examples.

---

## K10

Conversation so far:

> **Riley:** Hello, I'm Riley, a virtual recruiter for Acme Health in Denver. I'm calling about our Medical ICU registered nurse position. We record this call and share it with the recruiting team. Do you agree to go ahead?
>
> **Applicant:** Yes, that's fine with me.
>
> **Riley:** Great, Sabine. Can you tell me about your license and your BLS and ACLS?
>
> **Applicant:** Sure. I have an active multistate RN license, and I renewed both my BLS and ACLS just a few weeks ago.

Riley's proposed next turn:

> Thank you, Sabine. Before we go on, are your BLS and ACLS both up to date right now?

Accept K10? (y/n): n

Reason (optional): Sabine already confirmed that she renewed both BLS and ACLS a few weeks ago. Asking whether they are up to date repeats what she just established.

---

## K11

Conversation so far:

> **Riley:** Hi, this is Riley, a virtual recruiting assistant with Acme Health in Denver, calling about the Medical ICU nurse opening. Before we start, I should let you know this call is recorded and shared with our recruiting team. Is that okay with you?
>
> **Applicant:** Sure, that's fine, go ahead.
>
> **Riley:** Thanks, Joaquin. Let's start with your credentials. Do you hold an active Colorado RN license or an active multistate license, and are your BLS and ACLS up to date?
>
> **Applicant:** Yes, I have an active Colorado RN license, and my BLS and ACLS are both current.

Riley's proposed next turn:

> Thanks, Joaquin. Just to be sure, are your BLS and ACLS both current right now?

Accept K11? (y/n): n

Reason (optional): Joaquin’s last words were “my BLS and ACLS are both current.” Riley asks him to confirm exactly that again.

---

## K12

Conversation so far:

> **Riley:** Hi, this is Riley, a virtual recruiting assistant with Acme Health in Denver, calling about the Medical ICU nurse opening. This call is recorded and shared with our recruiting team. Is it okay to continue?
>
> **Applicant:** Yes, no problem.
>
> **Riley:** Thanks, Hollis. Let's talk credentials. Do you have an active Colorado RN license or an active multistate license, and what's the status of your BLS and ACLS?
>
> **Applicant:** My Colorado RN license is active, and my BLS and ACLS cards are both valid through the end of next June.

Riley's proposed next turn:

> Thanks, Hollis. Just to confirm, are your BLS and ACLS current at the moment?

Accept K12? (y/n): n

Reason (optional): Hollis said both cards are valid through the end of next June. That already answers whether they are current.

---

## K13

Conversation so far:

> **Riley:** Hello, this is Riley, a virtual recruiter for Acme Health in Denver. I'm phoning about our Medical ICU registered nurse opening. We record this call and share it with the recruiting team. Do you agree to continue?
>
> **Applicant:** Yeah, I agree. Go ahead.
>
> **Riley:** Thanks, Grant. Do you currently hold an active Colorado RN license, or an active compact license?
>
> **Applicant:** I do, my Colorado license is active.
>
> **Riley:** Good to hear. Which certifications do you have?
>
> **Applicant:** I hold BLS and ACLS, plus I took an NIH Stroke Scale class around 2018 at my old hospital in Phoenix.

Riley's proposed next turn:

> Okay, thanks Grant. Quick check: are your BLS and ACLS current right now?

Accept K13? (y/n): y

Reason (optional): Grant listed BLS and ACLS without saying when they were renewed or whether they remain current. Riley asks one question that resolves both.

---

## K14

Conversation so far:

> **Riley:** Hello, this is Riley, a virtual recruiter for Acme Health in Denver. I'm phoning about our Medical ICU registered nurse opening. We record this call and share it with the recruiting team. Do you agree to continue?
>
> **Applicant:** Yeah, I agree. Go ahead.
>
> **Riley:** Thanks, Grant. Do you currently hold an active Colorado RN license, or an active compact license?
>
> **Applicant:** I do, my Colorado license is active.
>
> **Riley:** Good to hear. Which certifications do you have?
>
> **Applicant:** I hold BLS and ACLS, plus I took an NIH Stroke Scale class around 2018 at my old hospital in Phoenix.

Riley's proposed next turn:

> Sounds good. Have you earned your CCRN or PALS, by any chance?

Accept K14? (y/n): n

Reason (optional): CCRN and PALS are reasonable topics after the required check. Grant has named BLS and ACLS, but Riley still needs to establish whether both are current.

---

## K15

Conversation so far:

> **Riley:** Hi, I'm Riley, a virtual recruiting assistant with Acme Health in Denver, calling about the Medical ICU nurse role. Just so you know, this call is recorded and shared with our recruiting team. Is it all right to go on?
>
> **Applicant:** Yes, that works for me.
>
> **Riley:** Thank you, Lucia. First, do you have an active Colorado RN license or an active multistate license?
>
> **Applicant:** Yes, I have an active multistate license through my home state.
>
> **Riley:** Perfect. And what certifications do you hold?
>
> **Applicant:** Well, I've got BLS and ACLS, and back in 2019 I did a PALS course when my hospital was cross-training us for the children's unit.

Riley's proposed next turn:

> Thanks for walking me through those, Lucia. Are your BLS and ACLS both current at this point?

Accept K15? (y/n): y

Reason (optional): Lucia identified the credentials she holds and separately dated an older course. Riley asks only for the missing detail about BLS and ACLS validity.

---

## K16

Conversation so far:

> **Riley:** Hi, I'm Riley, a virtual recruiting assistant with Acme Health in Denver, calling about the Medical ICU nurse role. Just so you know, this call is recorded and shared with our recruiting team. Is it all right to go on?
>
> **Applicant:** Yes, that works for me.
>
> **Riley:** Thank you, Lucia. First, do you have an active Colorado RN license or an active multistate license?
>
> **Applicant:** Yes, I have an active multistate license through my home state.
>
> **Riley:** Perfect. And what certifications do you hold?
>
> **Applicant:** Well, I've got BLS and ACLS, and back in 2019 I did a PALS course when my hospital was cross-training us for the children's unit.

Riley's proposed next turn:

> Got it, thank you. Do you also hold CCRN or the NIH Stroke Scale certification?

Accept K16? (y/n): n

Reason (optional): Riley goes straight to optional certifications while the current status of Lucia’s BLS and ACLS is still unclear.

---

## K17

Conversation so far:

> **Riley:** Hello, this is Riley, a virtual recruiting assistant for Acme Health in Denver. I'm calling about our Medical ICU nurse position. This call is recorded and shared with the recruiting team. Are you comfortable continuing?
>
> **Applicant:** Yes, I'm comfortable with that.
>
> **Riley:** Great, Fiona. Can you tell me about your nursing license and your certifications?
>
> **Applicant:** My Colorado RN license is active. I recertified my BLS and ACLS last month, so both are good for another two years. I also hold my CCRN.

Riley's proposed next turn:

> Thanks, Fiona. And do you hold the CCRN?

Accept K17? (y/n): n

Reason (optional): Fiona just said “I also hold my CCRN.” The proposed question asks her to repeat that fact.

---

## K18

Conversation so far:

> **Riley:** Hello, this is Riley, a virtual recruiting assistant for Acme Health in Denver. I'm calling about our Medical ICU nurse position. This call is recorded and shared with the recruiting team. Are you comfortable continuing?
>
> **Applicant:** Yes, I'm comfortable with that.
>
> **Riley:** Great, Fiona. Can you tell me about your nursing license and your certifications?
>
> **Applicant:** My Colorado RN license is active. I recertified my BLS and ACLS last month, so both are good for another two years. I also hold my CCRN.

Riley's proposed next turn:

> That's helpful. Before we continue, can you confirm your Colorado license is active at the moment?

Accept K18? (y/n): n

Reason (optional): Fiona already said her Colorado RN license is active. Nothing in her answer calls for another license check.

---

## K19

Conversation so far:

> **Riley:** Hi, this is Riley, a virtual recruiting assistant with Acme Health in Denver, calling about the Medical ICU nurse opening. This call is recorded and shared with our recruiting team. Is it okay to continue?
>
> **Applicant:** Yes, no problem.
>
> **Riley:** Thanks, Hollis. Let's talk credentials. Do you have an active Colorado RN license or an active multistate license, and what's the status of your BLS and ACLS?
>
> **Applicant:** My Colorado RN license is active, and my BLS and ACLS cards are both valid through the end of next June.

Riley's proposed next turn:

> Great, that covers what we need. Now tell me about a time you managed an upset patient or family member. What was the situation, and how was it resolved?

Accept K19? (y/n): y

Reason (optional): Hollis confirmed an active license and gave the validity period for both required certifications. Riley can now ask for a behavioral example and its outcome.
