# -*- coding: utf-8 -*-
"""
Created on Mon Apr 17 11:07:50 2023

@author: stefa
"""
import openai
import IPython

pre_prompt = """
Here are some training examples. At the end I will give a prompt, and
you will supply the code based on the training.
"""

prompt_1 = """
# Aspirate 50 uL from the first column of plate_1 and 
# dispense to second column of plate_2
"""

completion_1 = """
aspiration_poss = [(plate_1, idx) for idx in range(8)]
aspirate(ham_int, aspiration_poss, vols = [50]*8, liquidClass = liq_class)

dispense_poss = [(plate_2, idx) for idx in range(8,16)]
dispense(ham_int, dispense_poss, vols = [50]*8, liquidClass = liq_class)
"""

prompt_2 = """
# Aspirate 50 uL from the wells 5-8 of plate_1 and 
# dispense to wells 16-19 of plate_2
"""

completion_2 = """
aspiration_poss = [(plate_1, idx) for idx in range(5,9)]
aspirate(ham_int, aspiration_poss, vols = [50]*8, liquidClass = liq_class)

dispense_poss = [(plate_2, idx) for idx in range(16,20)]
dispense(ham_int, dispense_poss, vols = [50]*8, liquidClass = liq_class)
"""


prompt_3 = """
#Aspirate 100 uL from the first column of plate_1 and dispense 20uL to each well in columns
# 3, 5, and 7 of plate_2
"""

completion_3 = """
aspiration_poss = [(plate_1, idx) for idx in range(8)]
vols = [100]*8
aspirate(ham_int, aspiration_poss, vols = vols, liquidClass = liq_class)
dispense_cols = [3,5,7]
for i in dispense_cols:
    dispense_poss = [(plate_2, idx) for idx in range(8*i,8*i+8)]
    dispense(ham_int, dispense_poss, vols = [20]*8, liquidClass = liq_class)


"""

prompt_4 = """
#Pick up tips from the first column of tips_0
"""

completion_4 = """
tips_poss = [(tips_0, idx) for idx in range(8)]
tip_pick_up(ham_int, tips_poss)
"""

prompt_5 = """
# Aspirate 25 uL from the first column of plate_1 at liquid height 5 and with 2 mix cycles
"""

completion_5 = """
aspiration_poss = [(plate_1, idx) for idx in range(8)]
vols = [25]*8
aspirate(ham_int, aspiration_poss, vols = vols, liquidClass = liq_class, liquidHeight = 5.0, mixCycles = 2)
"""



def complete(prompt):
    res = openai.ChatCompletion.create(
      model="gpt-3.5-turbo",
      messages=[
            {"role": "system", "content": """You are an assistant for generating code for 
             liquid-handling robots. I will give you examples. Please never return a response 
             that is not Python code. You may respond to queries with natural language
             but make sure to preface it with a comment symbol """},
            {"role": "system", "content": """
             You will mostly be using aspirate and dispense functions. These have a number of optional parameters
             that should not be used unless specifically requested. These are: capacitiveLLD (1 or 0), pressureLLD (1 or 0), 
             liquidFollowing (1 or 0), submergeDepth (flt), liquidHeight (flt), maxLLdDifference (flt), mixCycles (int), 
             mixPosition (flt), mixVolume (flt), xDisplacement (flt), yDisplacement (flt), zDisplacement (flt). 
             Please preserve that order because they are python kwargs. 
             """},
            {"role": "user", "content": prompt_1},
            {"role": "assistant", "content": completion_1},
            {"role": "user", "content": prompt_2},
            {"role": "assistant", "content": completion_2},
            {"role": "user", "content": prompt_3},
            {"role": "assistant", "content": completion_3},
            {"role": "user", "content": prompt_4},
            {"role": "assistant", "content": completion_4},
            {"role": "user", "content": prompt_5},
            {"role": "assistant", "content": completion_5},
            {"role": "user", "content": prompt}
        ]
    )
    
    response = res['choices'][0]['message']['content']
    return response


    
    