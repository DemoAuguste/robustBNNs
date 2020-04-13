import argparse
import os
from directories import *
from utils import *
import torch
from torch import nn
import torch.nn.functional as nnf
import numpy as np
import torch.optim as torchopt
import torch.nn.functional as F


DEBUG = False


class NN(nn.Module):

    def __init__(self, dataset_name, input_shape, output_size, hidden_size, activation, 
                 architecture):
        super(NN, self).__init__()
        self.dataset_name = dataset_name
        self.criterion = nn.CrossEntropyLoss()
        self.architecture = architecture
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.activation = activation

        self.name = self.get_name(dataset_name, hidden_size, activation, architecture)
        self.set_model(architecture, activation, input_shape, output_size, hidden_size)
        # print("\nTotal number of network weights =", sum(p.numel() for p in self.parameters()))
        print("\nBase net:", self)

    def get_name(self, dataset_name, hidden_size, activation, architecture):
        return str(dataset_name)+"_nn_hid="+str(hidden_size)+"_act="+str(activation)+\
               "_arch="+str(architecture)

    def set_model(self, architecture, activation, input_shape, output_size, hidden_size):

        input_size = input_shape[0]*input_shape[1]*input_shape[2]
        in_channels = input_shape[0]
        n_classes = output_size

        if activation == "leaky":
            activ = nn.LeakyReLU
        elif activation == "sigm":
            activ = nn.Sigmoid
        elif activation == "tanh":
            activ = nn.Tanh

        if architecture == "fc":
            self.model = nn.Sequential(
                nn.Flatten(),
                nn.Linear(input_size, hidden_size),
                activ(),
                nn.Linear(hidden_size, n_classes))

        elif architecture == "fc2":
            self.model = nn.Sequential(
                nn.Flatten(),
                nn.Linear(input_size, hidden_size),
                activ(),
                nn.Linear(hidden_size, hidden_size),
                activ(),
                nn.Linear(hidden_size, n_classes))

        elif architecture == "conv":
            self.model = nn.Sequential(
                nn.Conv2d(in_channels, 32, kernel_size=5),
                activ(),
                nn.MaxPool2d(kernel_size=2),
                nn.Conv2d(32, hidden_size, kernel_size=5),
                activ(),
                nn.MaxPool2d(kernel_size=2, stride=1),
                nn.Flatten(),
                nn.Linear(int(hidden_size/(4*4))*input_size, output_size))
        else:
            raise NotImplementedError()

    def forward(self, inputs):
        x = self.model(inputs)
        return nn.Softmax(dim=-1)(x)

    def save(self, epochs, lr):
        name = self.name +"_ep="+str(epochs)+"_lr="+str(lr)

        os.makedirs(os.path.dirname(TESTS+name+"/"), exist_ok=True)
        print("\nSaving: ", TESTS+name+"/"+name+"_weights.pt")
        torch.save(self.state_dict(), TESTS+name+"/"+name+"_weights.pt")

        if DEBUG:
            print("\nCheck saved weights:")
            print("\nstate_dict()['l2.0.weight'] =", self.state_dict()["l2.0.weight"][0,0,:3])
            print("\nstate_dict()['out.weight'] =",self.state_dict()["out.weight"][0,:3])

    def load(self, epochs, lr, device, rel_path=TESTS):
        name = self.name +"_ep="+str(epochs)+"_lr="+str(lr)

        print("\nLoading: ", rel_path+name+"/"+name+"_weights.pt")
        self.load_state_dict(torch.load(rel_path+name+"/"+name+"_weights.pt"))
        print("\n", list(self.state_dict().keys()), "\n")
        self.to(device)

        if DEBUG:
            print("\nCheck loaded weights:")    
            print("\nstate_dict()['l2.0.weight'] =", self.state_dict()["l2.0.weight"][0,0,:3])
            print("\nstate_dict()['out.weight'] =",self.state_dict()["out.weight"][0,:3])

    def train(self, train_loader, epochs, lr, device):
        print("\n == NN training ==")
        random.seed(0)
        self.to(device)

        optimizer = torchopt.Adam(params=self.parameters(), lr=lr)

        start = time.time()
        for epoch in range(epochs):
            total_loss = 0.0
            correct_predictions = 0.0
            accuracy = 0.0
            total = 0.0
            n_inputs = 0

            for x_batch, y_batch in train_loader:
                n_inputs += len(x_batch)
                x_batch = x_batch.to(device)
                y_batch = y_batch.to(device).argmax(-1)
                total += y_batch.size(0)

                optimizer.zero_grad()
                outputs = self.forward(x_batch)
                loss = self.criterion(outputs, y_batch)
                loss.backward()
                optimizer.step()

                predictions = outputs.argmax(dim=1)
                total_loss += loss.data.item() / len(train_loader.dataset)
                correct_predictions += (predictions == y_batch).sum()
                accuracy = 100 * correct_predictions / len(train_loader.dataset)

            print(f"\n[Epoch {epoch + 1}]\t loss: {total_loss:.8f} \t accuracy: {accuracy:.2f}", 
                  end="\t")

        execution_time(start=start, end=time.time())
        self.save(epochs=epochs, lr=lr)

    def evaluate(self, test_loader, device):
        self.to(device)
        random.seed(0)

        with torch.no_grad():

            correct_predictions = 0.0

            for x_batch, y_batch in test_loader:

                x_batch = x_batch.to(device)
                y_batch = y_batch.to(device).argmax(-1)
                outputs = self(x_batch)
                predictions = outputs.argmax(dim=1)
                correct_predictions += (predictions == y_batch).sum()

            accuracy = 100 * correct_predictions / len(test_loader.dataset)
            print("\nAccuracy: %.2f%%" % (accuracy))
            return accuracy

def main(args):

    train_loader, test_loader, inp_shape, out_size = \
                            data_loaders(dataset_name=args.dataset, batch_size=128, 
                                         n_inputs=args.inputs, shuffle=True)

    dataset, epochs, lr, rel_path = (args.dataset, args.epochs, args.lr, TESTS)       
    # dataset, epochs, lr, rel_path = ("mnist", 20, 0.001, DATA)  

    nn = NN(dataset_name=dataset, input_shape=inp_shape, output_size=out_size, 
            hidden_size=args.hidden_size, activation=args.activation, architecture=args.architecture)
    nn.train(train_loader=train_loader, epochs=epochs, lr=lr, device=args.device)
    # nn.load(epochs=epochs, lr=lr, device=args.device, rel_path=rel_path)
    nn.evaluate(test_loader=test_loader, device=args.device)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Base NN")

    parser.add_argument("--inputs", default=100, type=int)
    parser.add_argument("--hidden_size", default=64, type=int, help="power of 2")
    parser.add_argument("--activation", default="leaky", type=str, help="leaky, sigm, tanh")
    parser.add_argument("--architecture", default="conv", type=str, help="conv, fc, fc2")
    parser.add_argument("--dataset", default="mnist", type=str, help="mnist, fashion_mnist, cifar")
    parser.add_argument("--lr", default=0.001, type=float)
    parser.add_argument("--epochs", default=10, type=int)
    parser.add_argument("--device", default='cpu', type=str, help="cpu, cuda")  

    main(args=parser.parse_args())