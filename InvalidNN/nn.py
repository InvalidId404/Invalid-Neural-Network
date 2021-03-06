from InvalidNN.core import *
from InvalidNN.utill.summary import variable_summary
import tensorflow as tf  # TODO: TORCH
import numpy as np
import multipledispatch


ACTIVATE = {
    'relu': tf.nn.relu,
    'softmax': tf.nn.softmax,
    'sigmoid': tf.nn.sigmoid
}


class Layer(Node):
    def __init__(self, name, upper, activate, dropout=False):
        super().__init__(name, upper)
        self.activate = ACTIVATE[activate]
        self.dropout = dropout


class Dense(Layer):
    def __init__(self, name, upper, activate, units, dropout=False):
        super().__init__(name, upper, activate, dropout)
        self.units = units
        self.weight = None
        self.bias = None

    def func(self, k):
        act = self.activate(
            tf.matmul(k, self.weight) + self.bias
        )
        return act  # if not self.dropout else tf.nn.dropout(act, keep_prob=self.upper.drop_p)


class NeuralNetwork(Graph):
    @abstractmethod
    def init_layers(self, layers, input_shape):
        pass  # Initialize Layers

    @abstractmethod
    def train(self, optimize, loss_fn, batch_size, epoch, learning_rate, label_length,
              train_data_generator, test_data_generator, drop_p=1.0):
        pass  # Train Network, TODO: Normalization Method 추가(Batch Norm 등)

    @abstractmethod
    def accuracy(self, test_data_generator):
        pass  # Test Network, TODO: 자유도 높게

    @abstractmethod
    def func(self, k):
        pass  # Query To Network


class TFNeuralNetwork(NeuralNetwork):
    def __init__(self, name, upper, input_shape: (list, tuple)):
        super().__init__(name, upper)
        self._layers = None
        self.output = None
        self.drop_p = tf.placeholder(tf.float32)
        with tf.name_scope(name) as scope:
            self.input_placeholder = tf.placeholder(shape=[None, *input_shape], dtype=tf.float32)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.submit_layers()

    def init_layers(self, layers, flow):
        # 초기화 메서드 정의
        @dispatch(Dense, object)
        def init(node, x):
            # 파라미터 초기화
            with tf.name_scope(node.name):
                with tf.name_scope('weight'):
                    node.weight = tf.Variable(dtype=tf.float32, initial_value=(tf.random_normal([
                        x.get_shape().as_list()[-1], node.units
                    ]) / tf.sqrt(float(node.units)) / (2 if node.activate == tf.nn.relu else 1)))
                    variable_summary(node.weight)
                with tf.name_scope('bias'):
                    node.bias = tf.Variable(tf.truncated_normal(dtype=tf.float32,
                                                                shape=[node.units]))
                    variable_summary(node.bias)
                activate = node(x)
                variable_summary(activate)
            return activate

        # 그래프 연결
        for layer in layers:
            flow = init(layer, flow)

        return flow

    def submit_layers(self):
        self.output = self.init_layers(self._layers, self.input_placeholder)
        return self.output

    def train(self, optimize, loss_fn, batch_size, epoch, learning_rate, label_class,
              train_data_generator, validation_data_generator,
              drop_p=1.0, summary_path='./summary', model_path='./model'):
        # 목표 출력값 플레이스홀더 정의
        object_output = tf.placeholder(tf.float32, [None, label_class])

        # 오차함수 정의 TODO: 더 많은 오차함수, 자유도 높이
        with tf.name_scope('loss'):
            if loss_fn == 'mse':
                loss = tf.reduce_mean(tf.square(object_output - self.output))
                tf.summary.scalar('MSE-loss', loss)
            elif loss_fn == 'cross-entropy':
                loss = -tf.reduce_sum(object_output * tf.log(tf.clip_by_value(self.output, 1e-30, 1.0)),
                                      name='cross-entropy-Loss')
                tf.summary.scalar('CE-loss', loss)

            else:
                loss = None
                print('error : loss Function not defined')
                exit()

        # 요약 작성
        merged = tf.summary.merge_all()

        # 정확도 계산
        with tf.name_scope('accuracy'):
            correct = tf.equal(
                tf.argmax(self.output, 1), tf.argmax(object_output, 1)
            )
            accuracy = (tf.reduce_mean(tf.cast(correct, tf.float32))) * 100
            tf.summary.scalar('accuracy', accuracy)

        # 옵티마이저 정의
        if optimize == 'gradient-descent':
            train_step = tf.train.GradientDescentOptimizer(learning_rate, name='GD-train').minimize(loss)
        elif optimize == 'adam':
            train_step = tf.train.AdamOptimizer(learning_rate, name='ADAM-train').minimize(loss)
        elif optimize == 'rms-prop':
            train_step = tf.train.RMSPropOptimizer(learning_rate, name='RMS-train').minimize(loss)
        else:
            train_step = None
            print('optimizer not defined')
            exit()
        # TODO: Train Progress 출력
        init = tf.global_variables_initializer()
        with tf.Session() as sess:
            train_writer = tf.summary.FileWriter(summary_path, sess.graph)

            sess.run(init)

            for step in range(epoch):
                x_batch = []
                y_batch = []
                for _ in range(batch_size):
                    x, y = next(train_data_generator)
                    x_batch.append(x)
                    y_batch.append(y)
                _, summary = sess.run([train_step, merged], feed_dict={
                    self.input_placeholder: x_batch,
                    object_output: y_batch,
                    self.drop_p: drop_p
                })
                if (step % 10) == 0:
                    summary, acc = sess.run([merged, accuracy], feed_dict={
                            self.input_placeholder: np.zeros([10, 2048], dtype=float),
                            object_output: y_batch,
                            self.drop_p: drop_p
                        })

                if (step % 1000) == 0:
                    pass
                train_writer.add_summary(summary, step)

    def accuracy(self, test_data_generator):
        return 0

    def func(self, input_data):
        return 0
