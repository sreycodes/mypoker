# Term Project
This is my attempt to understand [CRR](https://poker.cs.ualberta.ca/publications/NIPS07-cfr.pdf) as a part of my final project for [CS3243 - Intro to AI](https://nusmods.com/modules/CS3243/introduction-to-artificial-intelligence). I would like to thank <https://int8.io/counterfactual-regret-minimization-for-poker-ai/> for the comprehensive explanation.  

In this limited version, the user only allowed to raise for four times in one round street. For more information about the project, one can head over to <https://github.com/changhongyan123/mypoker>.  

## Suggestions

- Make AI better and extensive by changing branching scheme of chance nodes.
- Find a way to generate all possible scenarios for the algorithm.
- Compute nash equilibrium incrementally (will not make a huge time difference). The main time difference was obtained by playing / sampling games and updating the strategy together.
