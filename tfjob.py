# -*- coding: utf-8 -*-
"""tfjob.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1cubAUQEOz7dVaOpbFXKBb2s3jz6dyNOc
"""

from __future__ import absolute_import, division, print_function

import argparse
import json
import os
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import tensorflow_datasets as tfds
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models
from tensorflow.keras.optimizers import SGD, Adam, RMSprop
from keras import backend as K






def make_datasets_unbatched():
  BUFFER_SIZE = 10000

  # Scaling MNIST data from (0, 255] to (0., 1.]
  def scale(image, label):
    image = tf.cast(image, tf.float32)
    image /= 255
    return image, label

  datasets, _ = tfds.load(name='fashion_mnist', with_info=True, as_supervised=True)

  return datasets['train'].map(scale).cache().shuffle(BUFFER_SIZE)


def model(args):
  model = models.Sequential()
  model.add(
      layers.Conv2D(64, (3, 3), activation='relu', input_shape=(28, 28, 1)))
  model.add(layers.MaxPooling2D((2, 2)))
  model.add(layers.Conv2D(128, (3, 3), activation='relu'))
  model.add(layers.Flatten())
  model.add(layers.Dense(256, activation='relu'))
  model.add(layers.Dense(10, activation='softmax'))

  model.summary()
  opt = args.optimizer
  model.compile(optimizer=opt,
                loss='sparse_categorical_crossentropy',
                metrics=['accuracy'])
  K.set_value(model.optimizer.learning_rate, args.learning_rate)
  return model


def main(args):

  # MultiWorkerMirroredStrategy creates copies of all variables in the model's
  # layers on each device across all workers
  # if your GPUs don't support NCCL, replace "communication" with another
  strategy = tf.distribute.experimental.MultiWorkerMirroredStrategy(
      communication=tf.distribute.experimental.CollectiveCommunication.AUTO)

  BATCH_SIZE_PER_REPLICA = 64
  BATCH_SIZE = BATCH_SIZE_PER_REPLICA * strategy.num_replicas_in_sync

  with strategy.scope():
    ds_train = make_datasets_unbatched().batch(BATCH_SIZE).repeat()
    options = tf.data.Options()
    options.experimental_distribute.auto_shard_policy = \
        tf.data.experimental.AutoShardPolicy.DATA

    ds_train = ds_train.with_options(options)
    # Model building/compiling need to be within `strategy.scope()`.
    multi_worker_model = model(args)

  # Function for decaying the learning rate.
  # You can define any decay function you need.
  # Callback for printing the LR at the end of each epoch.
  class PrintLR(tf.keras.callbacks.Callback):

    def on_epoch_end(self, epoch, logs=None): #pylint: disable=no-self-use
      print('\nLearning rate for epoch {} is {}'.format(
        epoch + 1, multi_worker_model.optimizer.lr.numpy()))

  callbacks = [
      tf.keras.callbacks.TensorBoard(log_dir='./logs'),
      PrintLR()
   ]

  # Keras' `model.fit()` trains the model with specified number of epochs and
  # number of steps per epoch. Note that the numbers here are for demonstration
  # purposes only and may not sufficiently produce a model with good quality.
  multi_worker_model.fit(ds_train,
                         epochs=10,
                         steps_per_epoch=70,
                         callbacks=callbacks)

  # Saving a model
  model_path = args.saved_model_dir

  multi_worker_model.save(model_path)


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--saved_model_dir',
                      type=str,
                      required=True,
                      help='Tensorflow export directory.')
  parser.add_argument('--learning_rate', type=float, default=0.001,
                      help='Initial learning rate')
  parser.add_argument('--optimizer', type=str, required=True, default='adam',
                      help='optimizer')

  parsed_args = parser.parse_args()
  main(parsed_args)

