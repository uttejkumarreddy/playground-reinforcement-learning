import gym
import torch
import numpy as np
import copy
import matplotlib.pyplot as plt

from NormalModule import NormalModule
from ExperienceReplayBuffer import ExperienceReplayBuffer
from ActorNN import ActorNN
from CriticNN import CriticNN

from torch.distributions import Normal
from torch.optim import Adam

from collections import deque

class BasePPOAgent:
    def __init__(self):
        # Environment
        self.env = gym.make('Pendulum-v1')
        
        self.state = self.env.reset()

        # sample hyperparameters
        self.batch_size = 10
        self.epochs = 30
        self.learning_rate = 1e-3
        self.hidden_size = 8
        self.n_layers = 2

        # additional hyperparameters
        self.gamma = 0.99
        self.training_size = 100
        
        self.input_size = 3
        self.output_size = 1

        # Experience replay buffer
        self.replay_buffer = ExperienceReplayBuffer(self.training_size)

        # Actor and critic networks
        self.actor = ActorNN(self.input_size, self.output_size, self.hidden_size, self.n_layers)
        self.critic = CriticNN(self.input_size, self.output_size, self.hidden_size, self.n_layers)

        # Actor network copy for Surrogative objective
        self.actor_old = ActorNN(self.input_size, self.output_size, self.hidden_size, self.n_layers)

        # Actor and critic optimizers
        self.actor_optimizer = Adam(self.actor.parameters(), lr = self.learning_rate, eps = 1e-5)
        self.critic_optimizer = Adam(self.actor.parameters(), lr = self.learning_rate, eps = 1e-5)

        # Capture rewards and losses
        self.episodic_losses = []
        self.episodic_rewards = []
        self.episodic_advantage_estimates = []

    def train(self):
        for episode in range(self.epochs):
            state = self.env.reset()

            for timestep in range(self.training_size):
                # Task 1: Environment Interaction Loop
                # action = env.action_space.sample()

                # Task 2: Test experience replay buffer with random policy from gaussian distribution
                # normalModule = NormalModule(self.input_size, self.output_size)
                # mean, std = normalModule.forward(torch.as_tensor(state))
                # gaussianDist = Normal(mean, std)
                # action = gaussianDist.sample().item()

                mean, std = self.actor.forward(torch.as_tensor(state))
                normalDistribution = Normal(mean, std)
                action = normalDistribution.sample().item()

                # Apply action
                obs, reward, done, info = self.env.step([action])

                # Task 2: Store trajectory in experience replay buffer
                trajectory = [state, action, reward, obs]
                self.replay_buffer.append(trajectory)

                state = obs

            # Copy over the actor network before updating gradients
            with torch.no_grad():
                self.actor_old = copy.deepcopy(self.actor)

            # Calculate rewards-to-go for the trajectories in replay buffer
            self.episodic_rewards.append(self.calculate_reward_to_go(0))
            
            # Calculate advantage estimates for the trajectories in the replay buffer
            self.episodic_advantage_estimates.append(self.advantage_function(0))

            # Calculate losses
            actor_loss = self.actor_loss()
            critic_loss = self.critic_loss()

            # Enable requires_grad on critic loss
            critic_loss = torch.as_tensor([critic_loss])
            critic_loss.requires_grad_()

            # Calculate and store total loss
            total_loss = actor_loss - critic_loss
            self.episodic_losses.append(total_loss)

            # Update gradients
            self.actor_optimizer.zero_grad()
            actor_loss.backward()
            self.actor_optimizer.step()
            
            self.critic_optimizer.zero_grad()
            critic_loss.backward()
            self.critic_optimizer.step()

            self.env.render()

            self.replay_buffer.clear()

    # Task 3: Make episodic reward processing function
    def calculate_reward_to_go(self, fromTimestep):
        rewardToGo = 0
        for timestep in range(fromTimestep, len(self.replay_buffer.buffer)):
            trajectory = self.replay_buffer.buffer[timestep]
            reward = trajectory[2]
            rewardToGo += reward * (self.gamma ** timestep)
        return rewardToGo

    # Task 4: Vanilla Policy Gradient Agent
    def get_probability_of_action_in_state(self, state, action, usePreviousActor = False):
        mean, std = None, None
        if usePreviousActor:
            mean, std = self.actor_old.forward(torch.as_tensor(state))
        else:
            mean, std = self.actor.forward(torch.as_tensor(state))
        a = std * torch.sqrt(2 * torch.as_tensor(np.pi))
        b = torch.exp(-(action - mean)**2 / (2 * std**2))
        probability = 1 / (a * b)
        return probability

    # Task 6: Generalized Advantage
    def advantage_function(self, fromTimestep):
        advantage = 0

        critic_values = []
        for timestep in range(len(self.replay_buffer.buffer)):
            trajectory = self.replay_buffer.buffer[timestep]
            state = trajectory[0]
            critic_value = self.get_critic_value(state)
            critic_values.append(critic_value)

        for timestep in reversed(range(fromTimestep)):
            trajectory = self.replay_buffer.buffer[timestep]
            reward = trajectory[2]
            advantage += reward + (self.gamma * critic_values[timestep + 1]) - critic_values[timestep]

        return advantage

    # Task 7: Surrogate Objective Functions
    def action_ratio(self, state, action):
        probability_of_action_in_current_actor = self.get_probability_of_action_in_state(state, action)
        probability_of_action_in_old_actor = self.get_probability_of_action_in_state(state, action, True)
        return (probability_of_action_in_current_actor / probability_of_action_in_old_actor)

    def surrogate_loss_function(self):
        pass

    # Actor Functions
    def actor_loss(self):
        # Implemented in calling functions
        pass

    # Critic Functions
    def critic_loss(self):
        rewardsTrue = []
        rewardsToGo = []

        for timestep in range(len(self.replay_buffer.buffer)):
            trajectory = self.replay_buffer.buffer[timestep]
            rewardsTrue.append(trajectory[2])
            rewardsToGo.append(self.calculate_reward_to_go(timestep))

        rewardsTrue = np.array(rewardsTrue)
        rewardsToGo = np.array(rewardsToGo)
        mse = ((rewardsTrue - rewardsToGo) ** 2).mean()

        return mse

    def get_critic_value(self, state):
        return self.critic.forward(torch.as_tensor(state))

    def plot_episodic_losses(self):
        plt.plot(
            np.arange(self.training_size),
            torch.tensor(self.episodic_losses).detach().numpy()
        )
        plt.xlabel('Iterations')
        plt.xlabel('Losses')
        plt.show()

    def plot_episodic_rewards(self):
        plt.plot(
            np.arange(self.training_size),
            torch.tensor(self.episodic_rewards).detach().numpy()
        )
        plt.xlabel('Iterations')
        plt.xlabel('Reward to Go')
        plt.show()